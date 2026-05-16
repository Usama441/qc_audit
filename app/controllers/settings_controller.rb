class SettingsController < ApplicationController
  def show
    @setting = AuditSetting.instance
    @sections = AuditRuleCatalog.sections_with_states(@setting.resolved_enabled_rules)
  end

  def update
    setting = AuditSetting.instance
    setting.update!(enabled_rules: normalized_enabled_rules)

    redirect_to settings_path, notice: "Audit check settings updated."
  end

  def reset
    AuditSetting.instance.reset_to_defaults!

    redirect_to settings_path, notice: "Audit check settings reset to defaults."
  end

  private

  def normalized_enabled_rules
    submitted = params.fetch(:settings, {}).fetch(:enabled_rules, {})

    AuditRuleCatalog.rule_keys.to_h do |rule_key|
      [rule_key, ActiveModel::Type::Boolean.new.cast(submitted[rule_key])]
    end
  end
end
