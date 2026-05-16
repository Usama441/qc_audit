class AuditSetting < ApplicationRecord
  GLOBAL_KEY = "global".freeze

  validates :singleton_key, presence: true, uniqueness: true

  before_validation :assign_defaults

  class << self
    def instance
      find_or_initialize_by(singleton_key: GLOBAL_KEY).tap do |setting|
        setting.send(:assign_defaults)
      end
    end
  end

  def resolved_enabled_rules
    AuditRuleCatalog.normalize_enabled_rules(enabled_rules)
  end

  def reset_to_defaults!
    update!(enabled_rules: AuditRuleCatalog.default_enabled_rules)
  end

  def enabled_rule_count
    resolved_enabled_rules.count { |_rule_key, enabled| enabled }
  end

  private

  def assign_defaults
    self.singleton_key ||= GLOBAL_KEY
    self.enabled_rules = AuditRuleCatalog.default_enabled_rules if enabled_rules.blank?
  end
end
