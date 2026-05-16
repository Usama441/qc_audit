class CreatePythonJobs < ActiveRecord::Migration[8.1]
  def change
    create_table :python_jobs do |t|
      t.string :job_id
      t.string :task_name
      t.string :status
      t.jsonb :payload
      t.jsonb :result
      t.text :error_message
      t.datetime :started_at
      t.datetime :completed_at

      t.timestamps
    end
    add_index :python_jobs, :job_id, unique: true
  end
end
