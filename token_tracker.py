#!/usr/bin/env python3
"""
Token Tracking System for MeistroCraft
Monitors and manages API token usage for OpenAI and Anthropic APIs.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class ApiProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class UsageType(Enum):
    INPUT = "input"
    OUTPUT = "output"
    TOTAL = "total"


@dataclass
class TokenUsage:
    """Represents token usage for a single API call."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: str
    session_id: Optional[str] = None
    task_type: Optional[str] = None

    @classmethod
    def from_openai_response(
            cls,
            response: Any,
            model: str,
            session_id: Optional[str] = None,
            task_type: Optional[str] = None) -> 'TokenUsage':
        """Create TokenUsage from OpenAI API response."""
        usage = response.usage
        cost = cls._calculate_openai_cost(model, usage.prompt_tokens, usage.completion_tokens)

        return cls(
            provider=ApiProvider.OPENAI.value,
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=cost,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            task_type=task_type
        )

    @classmethod
    def from_anthropic_response(
            cls,
            response: Any,
            model: str,
            session_id: Optional[str] = None,
            task_type: Optional[str] = None) -> 'TokenUsage':
        """Create TokenUsage from Anthropic API response."""
        # Anthropic returns token usage in the response
        input_tokens = getattr(response.usage, 'input_tokens', 0)
        output_tokens = getattr(response.usage, 'output_tokens', 0)
        total_tokens = input_tokens + output_tokens
        cost = cls._calculate_anthropic_cost(model, input_tokens, output_tokens)

        return cls(
            provider=ApiProvider.ANTHROPIC.value,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            task_type=task_type
        )

    @staticmethod
    def _calculate_openai_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for OpenAI API usage based on current pricing."""
        # Pricing as of July 2025 (these should be updated regularly)
        pricing = {
            "gpt-4-0613": {"input": 0.03, "output": 0.06},  # per 1K tokens
            "gpt-4-1106-preview": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-1106": {"input": 0.001, "output": 0.002},
        }

        # Default pricing if model not found
        default_pricing = {"input": 0.01, "output": 0.03}
        model_pricing = pricing.get(model, default_pricing)

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]

        return round(input_cost + output_cost, 6)

    @staticmethod
    def _calculate_anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for Anthropic API usage based on current pricing."""
        # Pricing as of July 2025 (these should be updated regularly)
        pricing = {
            "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},  # per 1K tokens
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        }

        # Default pricing if model not found
        default_pricing = {"input": 0.003, "output": 0.015}
        model_pricing = pricing.get(model, default_pricing)

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]

        return round(input_cost + output_cost, 6)


@dataclass
class UsageSummary:
    """Summary of token usage over a time period."""
    provider: str
    period_start: str
    period_end: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    models_used: List[str]
    sessions: List[str]


@dataclass
class UsageLimits:
    """Token usage limits configuration."""
    daily_token_limit: Optional[int] = None
    monthly_token_limit: Optional[int] = None
    daily_cost_limit_usd: Optional[float] = None
    monthly_cost_limit_usd: Optional[float] = None
    per_session_token_limit: Optional[int] = None
    warn_at_percentage: float = 80.0  # Warn when usage reaches this % of limit


class TokenTracker:
    """Main token tracking and management class."""

    def __init__(self, storage_dir: str = "token_usage"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.usage_file = os.path.join(storage_dir, "usage_log.jsonl")
        self.limits_file = os.path.join(storage_dir, "limits.json")
        self.summary_file = os.path.join(storage_dir, "daily_summary.json")

        self.limits = self._load_limits()

    def track_usage(self, usage: TokenUsage) -> None:
        """Record a new token usage entry."""
        # Append to usage log
        with open(self.usage_file, 'a') as f:
            f.write(json.dumps(asdict(usage)) + '\n')

        # Check limits and warn if necessary
        self._check_limits(usage)

        # Update daily summary
        self._update_daily_summary(usage)

    def _load_limits(self) -> UsageLimits:
        """Load usage limits from configuration."""
        if os.path.exists(self.limits_file):
            with open(self.limits_file, 'r') as f:
                data = json.load(f)
                return UsageLimits(**data)
        return UsageLimits()

    def save_limits(self, limits: UsageLimits) -> None:
        """Save usage limits to configuration."""
        self.limits = limits
        with open(self.limits_file, 'w') as f:
            json.dump(asdict(limits), f, indent=2)

    def get_usage_summary(self,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None,
                          provider: Optional[str] = None) -> UsageSummary:
        """Get usage summary for a time period."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        usage_entries = self._load_usage_entries(start_date, end_date, provider)

        if not usage_entries:
            return UsageSummary(
                provider=provider or "all",
                period_start=start_date.isoformat(),
                period_end=end_date.isoformat(),
                total_requests=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_tokens=0,
                total_cost_usd=0.0,
                models_used=[],
                sessions=[]
            )

        total_input = sum(entry.input_tokens for entry in usage_entries)
        total_output = sum(entry.output_tokens for entry in usage_entries)
        total_cost = sum(entry.cost_usd for entry in usage_entries)
        models_used = list(set(entry.model for entry in usage_entries))
        sessions = list(set(entry.session_id for entry in usage_entries if entry.session_id))

        return UsageSummary(
            provider=provider or "all",
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            total_requests=len(usage_entries),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            total_cost_usd=round(total_cost, 4),
            models_used=models_used,
            sessions=sessions
        )

    def _load_usage_entries(self,
                            start_date: datetime,
                            end_date: datetime,
                            provider: Optional[str] = None) -> List[TokenUsage]:
        """Load usage entries from log file within date range."""
        entries = []

        if not os.path.exists(self.usage_file):
            return entries

        with open(self.usage_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    entry = TokenUsage(**data)
                    entry_time = datetime.fromisoformat(entry.timestamp)

                    if start_date <= entry_time <= end_date:
                        if provider is None or entry.provider == provider:
                            entries.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue

        return entries

    def _check_limits(self, usage: TokenUsage) -> None:
        """Check if usage exceeds limits and warn user."""
        if not self.limits:
            return

        # Check daily limits
        today = datetime.now().date()
        daily_summary = self.get_usage_summary(
            start_date=datetime.combine(today, datetime.min.time()),
            end_date=datetime.now(),
            provider=usage.provider
        )

        # Check token limits
        if self.limits.daily_token_limit:
            if daily_summary.total_tokens >= self.limits.daily_token_limit:
                print(
                    f"⚠️  Daily token limit exceeded! Used: {daily_summary.total_tokens}, "
                    f"Limit: {self.limits.daily_token_limit}")
            elif daily_summary.total_tokens >= self.limits.daily_token_limit * (self.limits.warn_at_percentage / 100):
                percentage = (daily_summary.total_tokens / self.limits.daily_token_limit) * 100
                print(
                    f"⚠️  Daily token usage at {percentage:.1f}% of limit ({daily_summary.total_tokens}/{self.limits.daily_token_limit})")

        # Check cost limits
        if self.limits.daily_cost_limit_usd:
            if daily_summary.total_cost_usd >= self.limits.daily_cost_limit_usd:
                print(
                    f"⚠️  Daily cost limit exceeded! Used: ${daily_summary.total_cost_usd:.4f}, "
                    f"Limit: ${self.limits.daily_cost_limit_usd:.4f}")
            elif daily_summary.total_cost_usd >= self.limits.daily_cost_limit_usd * (self.limits.warn_at_percentage / 100):
                percentage = (daily_summary.total_cost_usd / self.limits.daily_cost_limit_usd) * 100
                print(
                    f"⚠️  Daily cost usage at {percentage:.1f}% of limit (${daily_summary.total_cost_usd:.4f}/${self.limits.daily_cost_limit_usd:.4f})")

    def _update_daily_summary(self, usage: TokenUsage) -> None:
        """Update daily summary statistics."""
        today = datetime.now().date().isoformat()

        # Load existing summary
        summary_data = {}
        if os.path.exists(self.summary_file):
            with open(self.summary_file, 'r') as f:
                summary_data = json.load(f)

        # Initialize today's summary if not exists
        if today not in summary_data:
            summary_data[today] = {
                "openai": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
                "anthropic": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            }

        # Update summary
        provider_data = summary_data[today][usage.provider]
        provider_data["requests"] += 1
        provider_data["input_tokens"] += usage.input_tokens
        provider_data["output_tokens"] += usage.output_tokens
        provider_data["cost_usd"] = round(provider_data["cost_usd"] + usage.cost_usd, 6)

        # Save updated summary
        with open(self.summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)

    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get daily summary for a specific date."""
        if date is None:
            date = datetime.now()

        date_str = date.date().isoformat()

        if os.path.exists(self.summary_file):
            with open(self.summary_file, 'r') as f:
                summary_data = json.load(f)
                return summary_data.get(date_str, {})

        return {}

    def get_top_sessions_by_usage(self, limit: int = 10) -> List[Tuple[str, int, float]]:
        """Get top sessions by token usage."""
        session_usage = {}

        # Get last 30 days of usage
        start_date = datetime.now() - timedelta(days=30)
        entries = self._load_usage_entries(start_date, datetime.now())

        for entry in entries:
            if entry.session_id:
                if entry.session_id not in session_usage:
                    session_usage[entry.session_id] = {"tokens": 0, "cost": 0.0}
                session_usage[entry.session_id]["tokens"] += entry.total_tokens
                session_usage[entry.session_id]["cost"] += entry.cost_usd

        # Sort by token usage
        sorted_sessions = sorted(
            session_usage.items(),
            key=lambda x: x[1]["tokens"],
            reverse=True
        )

        return [(session_id, data["tokens"], data["cost"]) for session_id, data in sorted_sessions[:limit]]

    def export_usage_report(self, start_date: datetime, end_date: datetime, output_file: str) -> None:
        """Export detailed usage report to CSV file."""
        import csv

        entries = self._load_usage_entries(start_date, end_date)

        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Provider', 'Model', 'Session ID', 'Task Type',
                'Input Tokens', 'Output Tokens', 'Total Tokens', 'Cost USD'
            ])

            for entry in entries:
                writer.writerow([
                    entry.timestamp, entry.provider, entry.model, entry.session_id or '',
                    entry.task_type or '', entry.input_tokens, entry.output_tokens,
                    entry.total_tokens, entry.cost_usd
                ])

        print(f"Usage report exported to: {output_file}")

    def cleanup_old_logs(self, days_to_keep: int = 90) -> None:
        """Remove usage logs older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        if not os.path.exists(self.usage_file):
            return

        temp_file = self.usage_file + '.tmp'
        kept_count = 0
        removed_count = 0

        with open(self.usage_file, 'r') as infile, open(temp_file, 'w') as outfile:
            for line in infile:
                try:
                    data = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(data['timestamp'])

                    if entry_time >= cutoff_date:
                        outfile.write(line)
                        kept_count += 1
                    else:
                        removed_count += 1
                except (json.JSONDecodeError, ValueError, KeyError):
                    # Keep malformed entries to avoid data loss
                    outfile.write(line)
                    kept_count += 1

        # Replace original file with cleaned version
        os.replace(temp_file, self.usage_file)

        if removed_count > 0:
            print(f"Cleaned up {removed_count} old usage entries, kept {kept_count} entries")
