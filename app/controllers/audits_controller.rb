class AuditsController < ApplicationController
  def index
    @uploads = AuditUpload.order(created_at: :desc)
  end

  def new
    @upload = AuditUpload.new
  end

  def create
    @upload = AuditUpload.new(upload_params)
    @upload.check_settings_snapshot = AuditSetting.instance.resolved_enabled_rules

    if @upload.save
      begin
        ensure_processing_report!(@upload)
        file_path = ActiveStorage::Blob.service.path_for(@upload.excel_file.key)
        job_id = PythonWorkerClient.enqueue("audit_check", {
          upload_id: @upload.id,
          file_path:  file_path,
          original_filename: @upload.excel_file.filename.to_s,
          free_zone:  @upload.free_zone,
          enabled_rules: @upload.check_settings
        })
        @upload.update!(python_job_id: job_id)
        redirect_to audit_path(@upload), notice: "File uploaded. Running audit checks…"
      rescue StandardError => e
        Rails.logger.error("Failed to enqueue audit upload #{@upload.id}: #{e.class}: #{e.message}")
        persist_failed_upload!(@upload, "The audit job could not be started. #{e.message}")
        redirect_to audit_path(@upload), alert: "The file was uploaded, but the audit job could not be started."
      end
    else
      render :new, status: :unprocessable_entity
    end
  end

  def show
    @upload = AuditUpload.find(params[:id])
    @report = @upload.audit_report

    respond_to do |format|
      format.html
      format.json { render json: audit_show_payload(@upload, @report) }
    end
  end

  def retry_check
    @upload = AuditUpload.find(params[:id])
    check_key = params[:check_key].to_s
    check_label = AuditRuleCatalog.rule_label(check_key)

    unless check_label
      redirect_to audit_path(@upload), alert: "Unknown check selected for retry."
      return
    end

    unless @upload.check_settings.fetch(check_key, true)
      redirect_to audit_path(@upload), alert: "#{check_label} is disabled in Settings and cannot be retried."
      return
    end

    if @upload.status == "processing"
      redirect_to audit_path(@upload), alert: "An audit is already running for this upload."
      return
    end

    begin
      mark_check_processing!(@upload, check_key, check_label)
      file_path = ActiveStorage::Blob.service.path_for(@upload.excel_file.key)
      job_id = PythonWorkerClient.enqueue("retry_audit_check", {
        upload_id: @upload.id,
        file_path: file_path,
        original_filename: @upload.excel_file.filename.to_s,
        free_zone: @upload.free_zone,
        check_key: check_key,
        enabled_rules: @upload.check_settings
      })
      @upload.update!(status: "processing", python_job_id: job_id)
      redirect_to audit_path(@upload), notice: "#{check_label} retry started."
    rescue StandardError => e
      Rails.logger.error("Failed to retry check #{check_key} for upload #{@upload.id}: #{e.class}: #{e.message}")
      redirect_to audit_path(@upload), alert: "Could not start retry for #{check_label}."
    end
  end

  def retry_all_checks
    @upload = AuditUpload.find(params[:id])

    if @upload.status == "processing"
      redirect_to audit_path(@upload), alert: "An audit is already running for this upload."
      return
    end

    retryable_keys = retryable_check_keys(@upload.audit_report)
    if retryable_keys.empty?
      redirect_to audit_path(@upload), alert: "There are no retryable checks for this audit."
      return
    end

    begin
      mark_checks_processing!(@upload, retryable_keys)
      file_path = ActiveStorage::Blob.service.path_for(@upload.excel_file.key)
      job_id = PythonWorkerClient.enqueue("retry_audit_checks", {
        upload_id: @upload.id,
        file_path: file_path,
        original_filename: @upload.excel_file.filename.to_s,
        free_zone: @upload.free_zone,
        check_keys: retryable_keys,
        enabled_rules: @upload.check_settings
      })
      @upload.update!(status: "processing", python_job_id: job_id)
      redirect_to audit_path(@upload), notice: "Bulk retry started for #{retryable_keys.length} checks."
    rescue StandardError => e
      Rails.logger.error("Failed to bulk retry checks for upload #{@upload.id}: #{e.class}: #{e.message}")
      redirect_to audit_path(@upload), alert: "Could not start bulk retry."
    end
  end

  private

  def upload_params
    params.require(:audit_upload).permit(:free_zone, :excel_file)
  end

  def persist_failed_upload!(upload, message)
    upload.update!(status: "failed")

    report_attributes = {
      results: [
        {
          "check_name" => "Audit Processing",
          "category" => "System",
          "status" => "fail",
          "message" => message,
          "details" => {}
        }
      ],
      summary: {
        "total" => 1,
        "passed" => 0,
        "failed" => 1,
        "warnings" => 0,
        "skipped" => 0,
        "disabled" => 0,
        "state" => "failed",
        "current_check" => nil,
        "checks_total" => AuditRuleCatalog.rule_keys.length,
        "checks_completed" => 0,
        "check_progress" => build_check_progress(upload)
      }
    }

    if upload.audit_report
      upload.audit_report.update!(report_attributes)
    else
      upload.create_audit_report!(report_attributes)
    end
  end

  def ensure_processing_report!(upload)
    return if upload.audit_report.present?

    upload.create_audit_report!(
      results: [],
      summary: {
        "total" => 0,
        "passed" => 0,
        "failed" => 0,
        "warnings" => 0,
        "skipped" => 0,
        "disabled" => 0,
        "state" => "processing",
        "current_check" => nil,
        "checks_total" => AuditRuleCatalog.rule_keys.length,
        "checks_completed" => 0,
        "check_progress" => build_check_progress(upload)
      }
    )
  end

  def build_check_progress(upload)
    AuditRuleCatalog.progress_entries(upload.check_settings)
  end

  def mark_check_processing!(upload, check_key, check_label)
    report = upload.audit_report || ensure_processing_report!(upload)
    summary = (report.summary || {}).deep_dup
    progress = (summary["check_progress"] || build_check_progress(upload)).map do |step|
      step = step.deep_dup
      if step["key"] == check_key
        step["status"] = "processing"
        step["message"] = "Retry queued for #{check_label}."
        step["retryable"] = false
      end
      step
    end

    summary["state"] = "processing"
    summary["current_check"] = check_label
    summary["check_progress"] = progress
    report.update!(summary: summary)
  end

  def mark_checks_processing!(upload, check_keys)
    report = upload.audit_report || ensure_processing_report!(upload)
    summary = (report.summary || {}).deep_dup
    progress = (summary["check_progress"] || build_check_progress(upload)).map do |step|
      step = step.deep_dup
      if check_keys.include?(step["key"])
        step["status"] = "pending"
        step["message"] = "Queued for bulk retry."
        step["retryable"] = false
      end
      step
    end

    first_check = progress.find { |step| check_keys.include?(step["key"]) }
    if first_check
      first_check["status"] = "processing"
      first_check["message"] = "Bulk retry queued for #{first_check['label']}."
    end

    summary["state"] = "processing"
    summary["current_check"] = first_check&.dig("label")
    summary["check_progress"] = progress
    report.update!(summary: summary)
  end

  def retryable_check_keys(report)
    return [] if report.blank?

    report.check_progress.filter_map do |step|
      step["key"] if step["retryable"] && AuditRuleCatalog.rule?(step["key"])
    end
  end

  def audit_show_payload(upload, report)
    {
      processing: report&.processing? || false,
      status_badge_html: render_to_string(
        partial: "audits/status_badge",
        formats: [:html],
        locals: { upload: upload }
      ),
      live_progress_html: render_to_string(
        partial: "audits/live_progress",
        formats: [:html],
        locals: { report: report }
      ),
      results_html: render_to_string(
        partial: "audits/results",
        formats: [:html],
        locals: { upload: upload, report: report }
      )
    }
  end
end
