class CreateAuditReports < ActiveRecord::Migration[8.1]
  def change
    create_table :audit_reports do |t|
      t.references :audit_upload, null: false, foreign_key: true
      t.jsonb :results
      t.jsonb :summary

      t.timestamps
    end
  end
end
