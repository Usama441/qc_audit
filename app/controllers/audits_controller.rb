class AuditsController < ApplicationController
  def index
    @uploads = AuditUpload.order(created_at: :desc)
  end

  def new
    @upload = AuditUpload.new
  end

  def create
    @upload = AuditUpload.new(upload_params)

    if @upload.save
      begin
        ensure_processing_report!(@upload)
        file_path = ActiveStorage::Blob.service.path_for(@upload.excel_file.key)
        job_id = PythonWorkerClient.enqueue("audit_check", {
          upload_id: @upload.id,
          file_path:  file_path,
          original_filename: @upload.excel_file.filename.to_s,
          free_zone:  @upload.free_zone
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
    check_label = audit_step_labels.to_h[check_key]

    unless check_label
      redirect_to audit_path(@upload), alert: "Unknown check selected for retry."
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
        check_key: check_key
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
        check_keys: retryable_keys
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
        "state" => "failed",
        "current_check" => nil,
        "checks_total" => audit_step_labels.length,
        "checks_completed" => 0,
        "check_progress" => build_check_progress
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
        "state" => "processing",
        "current_check" => nil,
        "checks_total" => audit_step_labels.length,
        "checks_completed" => 0,
        "check_progress" => build_check_progress
      }
    )
  end

  def build_check_progress
    audit_step_labels.map do |key, label|
      {
        "key" => key,
        "label" => label,
        "status" => "pending",
        "outcome" => nil,
        "attempts" => 0,
        "max_attempts" => 2,
        "message" => "Waiting to run.",
        "retryable" => false
      }
    end
  end

  def audit_step_labels
    [
      ["general_ledger", "General Ledger vs Trial Balance"],
      ["trial_balance", "Trial Balance"],
      ["balance_sheet", "Balance Sheet"],
      ["profit_loss", "Profit & Loss"],
      ["equity_statement", "Equity Statement"],
      ["cash_flow", "Cash Flow"],
      ["prepayment", "Prepayment"],
      ["sales", "Sales"],
      ["sl_control", "SL Control"],
      ["pl_control", "PL Control"],
      ["bank_control", "Bank Control"],
      ["accruals", "Accruals"],
      ["share_capital", "Share Capital"],
      ["vat_control", "VAT Control"]
    ]
  end

  def mark_check_processing!(upload, check_key, check_label)
    report = upload.audit_report || ensure_processing_report!(upload)
    summary = (report.summary || {}).deep_dup
    progress = (summary["check_progress"] || build_check_progress).map do |step|
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
    progress = (summary["check_progress"] || build_check_progress).map do |step|
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
      step["key"] if step["retryable"]
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
