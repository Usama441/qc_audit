class AuditReport < ApplicationRecord
  belongs_to :audit_upload

  # results: [{ check_name, category, status, message, details }]
  # summary: { total, passed, failed, warnings, skipped }

  def checks_by_category
    (results || []).group_by { |r| r["category"] }
  end

  def check_progress
    (summary || {})["check_progress"] || []
  end

  def current_check
    (summary || {})["current_check"]
  end

  def checks_completed
    (summary || {})["checks_completed"].to_i
  end

  def checks_total
    (summary || {})["checks_total"].to_i
  end

  def processing?
    (summary || {})["state"] == "processing"
  end

  def passed  = (summary || {})["passed"].to_i
  def failed  = (summary || {})["failed"].to_i
  def warnings = (summary || {})["warnings"].to_i
  def skipped = (summary || {})["skipped"].to_i
  def disabled = (summary || {})["disabled"].to_i
  def total   = (summary || {})["total"].to_i
end
