class AddCheckSettingsSnapshotToAuditUploads < ActiveRecord::Migration[8.1]
  def change
    add_column :audit_uploads, :check_settings_snapshot, :jsonb, null: false, default: {}
  end
end
