class PythonWorkerClient
  QUEUE_KEY = "qc_audit:jobs"

  def self.enqueue(task_name, payload = {})
    job_id = SecureRandom.uuid
    python_job = PythonJob.create!(
      job_id:    job_id,
      task_name: task_name,
      status:    "pending",
      payload:   payload
    )

    REDIS.rpush(QUEUE_KEY, {
      id:          job_id,
      task:        task_name,
      payload:     payload,
      enqueued_at: Time.current.iso8601
    }.to_json)

    job_id
  rescue StandardError => e
    python_job&.update!(
      status: "failed",
      error_message: "Queue enqueue failed: #{e.message}",
      completed_at: Time.current
    )
    raise
  end
end
