class AuditUpload < ApplicationRecord
  FREE_ZONES  = %w[mainland freezone_10 freezone_5].freeze
  STATUSES    = %w[pending processing completed failed].freeze
  ALLOWED_EXCEL_EXTENSIONS = %w[xlsx].freeze
  ALLOWED_EXCEL_CONTENT_TYPES = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream"
  ].freeze
  MAX_EXCEL_FILE_SIZE = ENV.fetch("MAX_WORKBOOK_SIZE_MB", 30).to_i.megabytes

  has_one_attached :excel_file
  has_one :audit_report, dependent: :destroy

  validates :free_zone, inclusion: { in: FREE_ZONES }
  validates :status,    inclusion: { in: STATUSES }
  validates :excel_file, presence: true
  validate :excel_file_extension_is_supported, if: -> { excel_file.attached? }
  validate :excel_file_content_type_is_supported, if: -> { excel_file.attached? }
  validate :excel_file_size_is_within_limit, if: -> { excel_file.attached? }

  after_initialize :set_defaults, if: :new_record?

  def completed? = status == "completed"
  def failed?    = status == "failed"
  def pending?   = status == "pending"

  private

  def set_defaults
    self.status ||= "pending"
  end

  def excel_file_extension_is_supported
    extension = excel_file.blob.filename.extension_without_delimiter&.downcase
    return if ALLOWED_EXCEL_EXTENSIONS.include?(extension)

    errors.add(:excel_file, "must be a .xlsx workbook")
  end

  def excel_file_content_type_is_supported
    content_type = excel_file.blob.content_type
    return if ALLOWED_EXCEL_CONTENT_TYPES.include?(content_type)

    errors.add(:excel_file, "must be an Excel .xlsx workbook")
  end

  def excel_file_size_is_within_limit
    return if excel_file.blob.byte_size <= MAX_EXCEL_FILE_SIZE

    errors.add(:excel_file, "must be #{MAX_EXCEL_FILE_SIZE / 1.megabyte} MB or smaller")
  end
end
