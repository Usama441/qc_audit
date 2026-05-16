require "test_helper"

class AuditUploadTest < ActiveSupport::TestCase
  test "check_settings merges snapshot with defaults" do
    upload = AuditUpload.new(check_settings_snapshot: {
      "general_ledger.gl_vs_trial_balance" => false
    })

    assert_equal false, upload.check_settings["general_ledger.gl_vs_trial_balance"]
    assert_equal true, upload.check_settings["trial_balance.sum_of_balances_zero"]
  end
end
