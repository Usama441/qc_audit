require "test_helper"

class AuditSettingTest < ActiveSupport::TestCase
  test "resolved_enabled_rules falls back to catalog defaults" do
    setting = AuditSetting.new(singleton_key: "global", enabled_rules: {
      "general_ledger.gl_vs_trial_balance" => false
    })

    assert_equal false, setting.resolved_enabled_rules["general_ledger.gl_vs_trial_balance"]
    assert_equal true, setting.resolved_enabled_rules["trial_balance.sum_of_balances_zero"]
  end

  test "reset_to_defaults restores all rules to enabled" do
    setting = audit_settings(:global)
    setting.update!(enabled_rules: { "general_ledger.gl_vs_trial_balance" => false })

    setting.reset_to_defaults!

    assert_equal AuditRuleCatalog.default_enabled_rules, setting.reload.enabled_rules
  end
end
