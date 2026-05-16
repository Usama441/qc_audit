class CreateAuditUploads < ActiveRecord::Migration[8.1]
  def change
    create_table :audit_uploads do |t|
      t.string :free_zone
      t.string :status
      t.string :python_job_id

      t.timestamps
    end
  end
end
