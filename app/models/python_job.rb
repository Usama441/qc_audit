class PythonJob < ApplicationRecord
  STATUSES = %w[pending processing completed failed].freeze

  validates :job_id, presence: true, uniqueness: true
  validates :task_name, presence: true
  validates :status, inclusion: { in: STATUSES }

  scope :pending,    -> { where(status: "pending") }
  scope :processing, -> { where(status: "processing") }
  scope :completed,  -> { where(status: "completed") }
  scope :failed,     -> { where(status: "failed") }

  def completed?  = status == "completed"
  def failed?     = status == "failed"
  def processing? = status == "processing"
end
