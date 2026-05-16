require "test_helper"

class SettingsControllerTest < ActionDispatch::IntegrationTest
  test "show renders successfully" do
    get settings_path

    assert_response :success
  end

  test "update persists enabled rules" do
    patch settings_path, params: {
      settings: {
        enabled_rules: {
          "general_ledger.gl_vs_trial_balance" => "1"
        }
      }
    }

    assert_redirected_to settings_path
    assert_equal true, AuditSetting.instance.reload.enabled_rules["general_ledger.gl_vs_trial_balance"]
    assert_equal false, AuditSetting.instance.reload.enabled_rules["trial_balance.sum_of_balances_zero"]
  end
end
