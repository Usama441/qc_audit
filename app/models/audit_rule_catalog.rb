class AuditRuleCatalog
  CATALOG_PATH = Rails.root.join("python", "audit_rules.json")

  class << self
    def sections
      @sections ||= JSON.parse(CATALOG_PATH.read, symbolize_names: true).fetch(:sections)
    end

    def rules
      @rules ||= sections.flat_map do |section|
        section.fetch(:rules).map do |rule|
          rule.merge(
            section_key: section.fetch(:section_key),
            section_label: section.fetch(:section_label)
          )
        end
      end
    end

    def rule_map
      @rule_map ||= rules.index_by { |rule| rule.fetch(:rule_key) }
    end

    def rule_keys
      @rule_keys ||= rules.map { |rule| rule.fetch(:rule_key) }
    end

    def default_enabled_rules
      @default_enabled_rules ||= rules.to_h do |rule|
        [rule.fetch(:rule_key), rule.fetch(:default_enabled, true)]
      end
    end

    def rule?(rule_key)
      rule_map.key?(rule_key.to_s)
    end

    def rule_label(rule_key)
      rule_map.dig(rule_key.to_s, :rule_label)
    end

    def progress_entries(enabled_rules = default_enabled_rules)
      resolved = normalize_enabled_rules(enabled_rules)

      rules.map do |rule|
        enabled = resolved.fetch(rule.fetch(:rule_key), true)

        {
          "key" => rule.fetch(:rule_key),
          "label" => rule.fetch(:rule_label),
          "section_key" => rule.fetch(:section_key),
          "section_label" => rule.fetch(:section_label),
          "enabled" => enabled,
          "status" => "pending",
          "outcome" => nil,
          "attempts" => 0,
          "max_attempts" => 2,
          "message" => enabled ? "Waiting to run." : "Disabled in Settings.",
          "retryable" => false
        }
      end
    end

    def normalize_enabled_rules(enabled_rules)
      default_enabled_rules.merge((enabled_rules || {}).to_h.stringify_keys.transform_values do |value|
        ActiveModel::Type::Boolean.new.cast(value)
      end)
    end

    def sections_with_states(enabled_rules)
      resolved = normalize_enabled_rules(enabled_rules)

      sections.map do |section|
        section_rules = section.fetch(:rules).map do |rule|
          {
            rule_key: rule.fetch(:rule_key),
            rule_label: rule.fetch(:rule_label),
            description: rule[:description],
            enabled: resolved.fetch(rule.fetch(:rule_key), true)
          }
        end

        {
          section_key: section.fetch(:section_key),
          section_label: section.fetch(:section_label),
          rules: section_rules,
          enabled_count: section_rules.count { |rule| rule[:enabled] },
          total_count: section_rules.length
        }
      end
    end

    def reset_cache!
      @sections = nil
      @rules = nil
      @rule_map = nil
      @rule_keys = nil
      @default_enabled_rules = nil
    end
  end
end
