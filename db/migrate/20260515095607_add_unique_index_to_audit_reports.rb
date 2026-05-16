class AddUniqueIndexToAuditReports < ActiveRecord::Migration[8.1]
  def change
    # belongs_to already created a non-unique index; replace with unique
    remove_index :audit_reports, :audit_upload_id, if_exists: true
    add_index    :audit_reports, :audit_upload_id, unique: true
  end
end
