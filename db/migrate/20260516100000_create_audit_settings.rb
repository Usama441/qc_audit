class CreateAuditSettings < ActiveRecord::Migration[8.1]
  def change
    create_table :audit_settings do |t|
      t.string :singleton_key, null: false
      t.jsonb :enabled_rules, null: false, default: {}

      t.timestamps
    end

    add_index :audit_settings, :singleton_key, unique: true
  end
end
