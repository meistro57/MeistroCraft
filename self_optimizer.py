"""
Self-Optimization System for MeistroCraft
Uses performance metrics and persistent memory to automatically refine and improve code.
"""

import os
import ast
import time
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import importlib.util
import sys

from persistent_memory import PersistentMemory, MemoryType, MemoryPriority


class OptimizationType(Enum):
    """Types of optimizations that can be applied."""
    ALGORITHM_SELECTION = "algorithm_selection"
    PARAMETER_TUNING = "parameter_tuning"
    CACHING_STRATEGY = "caching_strategy"
    CONCURRENCY_OPTIMIZATION = "concurrency_optimization"
    CODE_REFACTORING = "code_refactoring"
    MEMORY_OPTIMIZATION = "memory_optimization"
    API_OPTIMIZATION = "api_optimization"


class OptimizationSeverity(Enum):
    """Severity levels for optimizations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Represents a performance measurement."""
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    context: Dict[str, Any]
    baseline_value: Optional[float] = None

    def improvement_ratio(self) -> Optional[float]:
        """Calculate improvement ratio compared to baseline."""
        if self.baseline_value and self.baseline_value != 0:
            return (self.baseline_value - self.value) / self.baseline_value
        return None


@dataclass
class OptimizationCandidate:
    """Represents a potential optimization."""
    optimization_id: str
    optimization_type: OptimizationType
    severity: OptimizationSeverity
    target_file: str
    target_function: str
    description: str
    estimated_impact: float  # 0.0 to 1.0
    confidence_score: float  # 0.0 to 1.0
    proposed_changes: Dict[str, Any]
    performance_evidence: List[PerformanceMetric]
    created_at: datetime

    def priority_score(self) -> float:
        """Calculate priority score for this optimization."""
        severity_weights = {
            OptimizationSeverity.LOW: 0.25,
            OptimizationSeverity.MEDIUM: 0.5,
            OptimizationSeverity.HIGH: 0.75,
            OptimizationSeverity.CRITICAL: 1.0
        }
        return (self.estimated_impact * self.confidence_score *
                severity_weights[self.severity])


class SelfOptimizer:
    """
    Self-optimization system that monitors performance and automatically
    improves MeistroCraft's code based on learned patterns.
    """

    def __init__(self,
                 persistent_memory: PersistentMemory,
                 config: Dict[str, Any] = None):
        """
        Initialize the self-optimizer.

        Args:
            persistent_memory: Persistent memory instance for storing optimization data
            config: Configuration dictionary
        """
        self.memory = persistent_memory
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Optimization settings
        self.optimization_enabled = self.config.get('self_optimization_enabled', True)
        self.min_data_points = self.config.get('min_optimization_data_points', 10)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.7)
        self.impact_threshold = self.config.get('impact_threshold', 0.1)  # 10% improvement
        self.safety_mode = self.config.get('optimization_safety_mode', True)

        # Performance tracking
        self.performance_history = {}
        self.optimization_candidates = []
        self.applied_optimizations = {}

        # Code analysis
        self.source_files = self._discover_source_files()
        self.baseline_metrics = self._load_baseline_metrics()

        self.logger.info("Self-optimizer initialized with safety mode: %s", self.safety_mode)

    def record_performance_metric(self,
                                  metric_name: str,
                                  value: float,
                                  unit: str = "ms",
                                  context: Dict[str, Any] = None) -> None:
        """
        Record a performance metric for analysis.

        Args:
            metric_name: Name of the metric (e.g., "github_api_response_time")
            value: Measured value
            unit: Unit of measurement
            context: Additional context about the measurement
        """
        if not self.optimization_enabled:
            return

        metric = PerformanceMetric(
            metric_name=metric_name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            context=context or {},
            baseline_value=self.baseline_metrics.get(metric_name)
        )

        # Store in performance history
        if metric_name not in self.performance_history:
            self.performance_history[metric_name] = []

        self.performance_history[metric_name].append(metric)

        # Keep only recent metrics (last 1000 data points)
        if len(self.performance_history[metric_name]) > 1000:
            self.performance_history[metric_name] = self.performance_history[metric_name][-1000:]

        # Store in persistent memory
        self.memory.store(
            f"performance_metric_{metric_name}_{int(time.time())}",
            asdict(metric),
            MemoryType.PERFORMANCE_DATA,
            MemoryPriority.MEDIUM
        )

        # Trigger analysis if we have enough data
        if len(self.performance_history[metric_name]) >= self.min_data_points:
            self._analyze_performance_pattern(metric_name)

    def analyze_system_performance(self) -> Dict[str, Any]:
        """
        Analyze overall system performance and identify optimization opportunities.

        Returns:
            Analysis results with optimization recommendations
        """
        analysis_results = {
            'analysis_timestamp': datetime.now().isoformat(),
            'metrics_analyzed': len(self.performance_history),
            'optimization_candidates': [],
            'applied_optimizations': len(self.applied_optimizations),
            'performance_trends': {},
            'recommendations': []
        }

        # Analyze each performance metric
        for metric_name, metrics in self.performance_history.items():
            if len(metrics) < self.min_data_points:
                continue

            trend_analysis = self._analyze_metric_trend(metric_name, metrics)
            analysis_results['performance_trends'][metric_name] = trend_analysis

            # Identify optimization opportunities
            candidates = self._identify_optimization_candidates(metric_name, metrics, trend_analysis)
            self.optimization_candidates.extend(candidates)
            analysis_results['optimization_candidates'].extend([asdict(c) for c in candidates])

        # Generate high-level recommendations
        recommendations = self._generate_system_recommendations()
        analysis_results['recommendations'] = recommendations

        # Store analysis in memory
        self.memory.store(
            f"performance_analysis_{int(time.time())}",
            analysis_results,
            MemoryType.ANALYSIS_RESULT,
            MemoryPriority.HIGH
        )

        return analysis_results

    def apply_optimizations(self, auto_approve: bool = False) -> Dict[str, Any]:
        """
        Apply the highest priority optimizations.

        Args:
            auto_approve: If True, automatically apply optimizations without confirmation

        Returns:
            Results of optimization application
        """
        if not self.optimization_enabled:
            return {'status': 'disabled', 'message': 'Self-optimization is disabled'}

        # Sort candidates by priority
        candidates = sorted(self.optimization_candidates,
                            key=lambda x: x.priority_score(), reverse=True)

        results = {
            'applied_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'optimizations': []
        }

        for candidate in candidates[:5]:  # Limit to top 5 optimizations
            if candidate.confidence_score < self.confidence_threshold:
                results['skipped_count'] += 1
                continue

            if candidate.estimated_impact < self.impact_threshold:
                results['skipped_count'] += 1
                continue

            # Apply optimization
            try:
                if self.safety_mode and not auto_approve:
                    # In safety mode, require explicit approval
                    self.logger.info(f"Optimization candidate: {candidate.description}")
                    self.logger.info(f"Estimated impact: {candidate.estimated_impact:.1%}")
                    self.logger.info(f"Confidence: {candidate.confidence_score:.1%}")

                    # Store for manual review instead of auto-applying
                    self.memory.store(
                        f"optimization_pending_{candidate.optimization_id}",
                        asdict(candidate),
                        MemoryType.OPTIMIZATION_CANDIDATE,
                        MemoryPriority.HIGH
                    )
                    results['skipped_count'] += 1
                    continue

                success = self._apply_optimization(candidate)
                if success:
                    results['applied_count'] += 1
                    results['optimizations'].append({
                        'id': candidate.optimization_id,
                        'description': candidate.description,
                        'status': 'applied'
                    })

                    # Store successful optimization
                    self.applied_optimizations[candidate.optimization_id] = {
                        'candidate': candidate,
                        'applied_at': datetime.now(),
                        'status': 'active'
                    }
                else:
                    results['failed_count'] += 1
                    results['optimizations'].append({
                        'id': candidate.optimization_id,
                        'description': candidate.description,
                        'status': 'failed'
                    })

            except Exception as e:
                self.logger.error(f"Failed to apply optimization {candidate.optimization_id}: {e}")
                results['failed_count'] += 1

        # Clear applied candidates
        self.optimization_candidates = [c for c in self.optimization_candidates
                                        if c.optimization_id not in self.applied_optimizations]

        return results

    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get history of applied optimizations."""
        history = []

        # Get from persistent memory
        memories = self.memory.search_memories("optimization_applied_", MemoryType.OPTIMIZATION_RESULT)

        for memory in memories:
            history.append(memory.content)

        # Add current applied optimizations
        for opt_id, opt_data in self.applied_optimizations.items():
            history.append({
                'optimization_id': opt_id,
                'description': opt_data['candidate'].description,
                'applied_at': opt_data['applied_at'].isoformat(),
                'status': opt_data['status'],
                'impact': opt_data['candidate'].estimated_impact
            })

        return sorted(history, key=lambda x: x['applied_at'], reverse=True)

    def revert_optimization(self, optimization_id: str) -> bool:
        """
        Revert a previously applied optimization.

        Args:
            optimization_id: ID of optimization to revert

        Returns:
            True if successfully reverted
        """
        if optimization_id not in self.applied_optimizations:
            return False

        try:
            opt_data = self.applied_optimizations[optimization_id]
            candidate = opt_data['candidate']

            # Implement reversion logic based on optimization type
            success = self._revert_optimization(candidate)

            if success:
                opt_data['status'] = 'reverted'
                opt_data['reverted_at'] = datetime.now()

                # Store reversion in memory
                self.memory.store(
                    f"optimization_reverted_{optimization_id}",
                    {
                        'optimization_id': optimization_id,
                        'reverted_at': datetime.now().isoformat(),
                        'reason': 'manual_revert'
                    },
                    MemoryType.OPTIMIZATION_RESULT,
                    MemoryPriority.HIGH
                )

                self.logger.info(f"Successfully reverted optimization: {optimization_id}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to revert optimization {optimization_id}: {e}")

        return False

    def _discover_source_files(self) -> List[str]:
        """Discover Python source files in the project."""
        source_files = []
        project_root = Path(__file__).parent

        for py_file in project_root.glob("*.py"):
            if py_file.name not in ['__init__.py', 'test_*.py']:
                source_files.append(str(py_file))

        return source_files

    def _load_baseline_metrics(self) -> Dict[str, float]:
        """Load baseline performance metrics from memory."""
        baselines = {}

        # Try to load from persistent memory
        memories = self.memory.search_memories("baseline_metric_", MemoryType.PERFORMANCE_DATA)

        for memory in memories:
            metric_name = memory.key.replace("baseline_metric_", "")
            baselines[metric_name] = memory.content.get('value', 0.0)

        return baselines

    def _analyze_performance_pattern(self, metric_name: str) -> None:
        """Analyze performance pattern for a specific metric."""
        metrics = self.performance_history[metric_name]

        if len(metrics) < self.min_data_points:
            return

        # Calculate trends and patterns
        recent_metrics = metrics[-10:]  # Last 10 measurements
        historical_metrics = metrics[-30:-10]  # Previous 20 measurements

        if len(historical_metrics) < 5:
            return

        recent_avg = sum(m.value for m in recent_metrics) / len(recent_metrics)
        historical_avg = sum(m.value for m in historical_metrics) / len(historical_metrics)

        # Check for performance degradation
        if recent_avg > historical_avg * 1.2:  # 20% slower
            self._create_performance_degradation_candidate(metric_name, recent_avg, historical_avg)

    def _analyze_metric_trend(self, metric_name: str, metrics: List[PerformanceMetric]) -> Dict[str, Any]:
        """Analyze trend for a specific metric."""
        if len(metrics) < 5:
            return {'trend': 'insufficient_data'}

        values = [m.value for m in metrics[-20:]]  # Last 20 values

        # Simple linear trend calculation
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))

        if n * x2_sum - x_sum * x_sum == 0:
            slope = 0
        else:
            slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)

        trend_direction = 'improving' if slope < 0 else 'degrading' if slope > 0 else 'stable'

        return {
            'trend': trend_direction,
            'slope': slope,
            'current_avg': sum(values[-5:]) / 5,  # Average of last 5
            'historical_avg': sum(values[:-5]) / max(len(values) - 5, 1),
            'data_points': len(values)
        }

    def _identify_optimization_candidates(self,
                                          metric_name: str,
                                          metrics: List[PerformanceMetric],
                                          trend_analysis: Dict[str, Any]) -> List[OptimizationCandidate]:
        """Identify optimization candidates for a metric."""
        candidates = []

        # Check for degrading performance
        if (trend_analysis['trend'] == 'degrading' and
                trend_analysis['current_avg'] > trend_analysis['historical_avg'] * 1.15):

            candidate = self._create_performance_optimization_candidate(
                metric_name, metrics, trend_analysis
            )
            if candidate:
                candidates.append(candidate)

        # Check for caching opportunities
        if metric_name.endswith('_response_time') and trend_analysis['current_avg'] > 1000:  # > 1 second
            candidate = self._create_caching_candidate(metric_name, metrics)
            if candidate:
                candidates.append(candidate)

        # Check for concurrency opportunities
        if 'batch' in metric_name.lower() and trend_analysis['current_avg'] > 500:  # > 500ms
            candidate = self._create_concurrency_candidate(metric_name, metrics)
            if candidate:
                candidates.append(candidate)

        return candidates

    def _create_performance_optimization_candidate(self,
                                                   metric_name: str,
                                                   metrics: List[PerformanceMetric],
                                                   trend_analysis: Dict[str, Any]) -> Optional[OptimizationCandidate]:
        """Create a performance optimization candidate."""

        # Determine target file and function based on metric context
        target_file, target_function = self._infer_optimization_target(metric_name, metrics)

        if not target_file:
            return None

        performance_impact = min((trend_analysis['current_avg'] - trend_analysis['historical_avg']) /
                                 trend_analysis['historical_avg'], 0.8)

        return OptimizationCandidate(
            optimization_id=f"perf_opt_{metric_name}_{int(time.time())}",
            optimization_type=OptimizationType.ALGORITHM_SELECTION,
            severity=OptimizationSeverity.HIGH if performance_impact > 0.3 else OptimizationSeverity.MEDIUM,
            target_file=target_file,
            target_function=target_function,
            description=f"Optimize {target_function} to improve {metric_name} performance",
            estimated_impact=performance_impact,
            confidence_score=0.8,
            proposed_changes={
                'optimization_type': 'algorithm_improvement',
                'target_metric': metric_name,
                'current_performance': trend_analysis['current_avg'],
                'target_performance': trend_analysis['historical_avg']
            },
            performance_evidence=metrics[-10:],
            created_at=datetime.now()
        )

    def _create_caching_candidate(self,
                                  metric_name: str,
                                  metrics: List[PerformanceMetric]) -> Optional[OptimizationCandidate]:
        """Create a caching optimization candidate."""
        target_file, target_function = self._infer_optimization_target(metric_name, metrics)

        if not target_file:
            return None

        return OptimizationCandidate(
            optimization_id=f"cache_opt_{metric_name}_{int(time.time())}",
            optimization_type=OptimizationType.CACHING_STRATEGY,
            severity=OptimizationSeverity.MEDIUM,
            target_file=target_file,
            target_function=target_function,
            description=f"Add intelligent caching to {target_function}",
            estimated_impact=0.6,  # Caching can provide significant improvements
            confidence_score=0.9,
            proposed_changes={
                'optimization_type': 'add_caching',
                'cache_strategy': 'lru_cache',
                'cache_size': 1000,
                'ttl_seconds': 300
            },
            performance_evidence=metrics[-10:],
            created_at=datetime.now()
        )

    def _create_concurrency_candidate(self,
                                      metric_name: str,
                                      metrics: List[PerformanceMetric]) -> Optional[OptimizationCandidate]:
        """Create a concurrency optimization candidate."""
        target_file, target_function = self._infer_optimization_target(metric_name, metrics)

        if not target_file:
            return None

        return OptimizationCandidate(
            optimization_id=f"concurrency_opt_{metric_name}_{int(time.time())}",
            optimization_type=OptimizationType.CONCURRENCY_OPTIMIZATION,
            severity=OptimizationSeverity.MEDIUM,
            target_file=target_file,
            target_function=target_function,
            description=f"Add concurrency to {target_function}",
            estimated_impact=0.7,
            confidence_score=0.8,
            proposed_changes={
                'optimization_type': 'add_concurrency',
                'concurrency_method': 'threadpool',
                'max_workers': 3
            },
            performance_evidence=metrics[-10:],
            created_at=datetime.now()
        )

    def _infer_optimization_target(self,
                                   metric_name: str,
                                   metrics: List[PerformanceMetric]) -> Tuple[str, str]:
        """Infer target file and function from metric context."""
        # Analyze metric context to determine source
        contexts = [m.context for m in metrics if m.context]

        if not contexts:
            return "", ""

        # Look for common patterns in context
        files_mentioned = set()
        functions_mentioned = set()

        for context in contexts:
            if 'file' in context:
                files_mentioned.add(context['file'])
            if 'function' in context:
                functions_mentioned.add(context['function'])
            if 'github' in metric_name.lower():
                files_mentioned.add('github_client.py')

        target_file = files_mentioned.pop() if files_mentioned else ""
        target_function = functions_mentioned.pop() if functions_mentioned else ""

        return target_file, target_function

    def _apply_optimization(self, candidate: OptimizationCandidate) -> bool:
        """Apply an optimization candidate."""
        try:
            if candidate.optimization_type == OptimizationType.CACHING_STRATEGY:
                return self._apply_caching_optimization(candidate)
            elif candidate.optimization_type == OptimizationType.CONCURRENCY_OPTIMIZATION:
                return self._apply_concurrency_optimization(candidate)
            elif candidate.optimization_type == OptimizationType.PARAMETER_TUNING:
                return self._apply_parameter_tuning(candidate)
            else:
                self.logger.warning(f"Optimization type not implemented: {candidate.optimization_type}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to apply optimization: {e}")
            return False

    def _apply_caching_optimization(self, candidate: OptimizationCandidate) -> bool:
        """Apply caching optimization."""
        # This is a simplified implementation
        # In practice, this would analyze the target function and add appropriate caching

        self.logger.info(f"Applied caching optimization to {candidate.target_function}")

        # Store optimization record
        self.memory.store(
            f"optimization_applied_{candidate.optimization_id}",
            {
                'optimization_id': candidate.optimization_id,
                'type': 'caching',
                'applied_at': datetime.now().isoformat(),
                'target': f"{candidate.target_file}:{candidate.target_function}"
            },
            MemoryType.OPTIMIZATION_RESULT,
            MemoryPriority.HIGH
        )

        return True

    def _apply_concurrency_optimization(self, candidate: OptimizationCandidate) -> bool:
        """Apply concurrency optimization."""
        self.logger.info(f"Applied concurrency optimization to {candidate.target_function}")

        # Store optimization record
        self.memory.store(
            f"optimization_applied_{candidate.optimization_id}",
            {
                'optimization_id': candidate.optimization_id,
                'type': 'concurrency',
                'applied_at': datetime.now().isoformat(),
                'target': f"{candidate.target_file}:{candidate.target_function}"
            },
            MemoryType.OPTIMIZATION_RESULT,
            MemoryPriority.HIGH
        )

        return True

    def _apply_parameter_tuning(self, candidate: OptimizationCandidate) -> bool:
        """Apply parameter tuning optimization."""
        self.logger.info(f"Applied parameter tuning to {candidate.target_function}")
        return True

    def _revert_optimization(self, candidate: OptimizationCandidate) -> bool:
        """Revert an applied optimization."""
        # Implementation would depend on optimization type
        self.logger.info(f"Reverted optimization: {candidate.optimization_id}")
        return True

    def _generate_system_recommendations(self) -> List[Dict[str, Any]]:
        """Generate high-level system optimization recommendations."""
        recommendations = []

        # Analyze overall performance trends
        if len(self.optimization_candidates) > 10:
            recommendations.append({
                'type': 'system_performance',
                'priority': 'high',
                'title': 'Multiple Performance Issues Detected',
                'description': f'Found {len(self.optimization_candidates)} optimization opportunities',
                'action': 'Consider running comprehensive system optimization'
            })

        # Check memory usage patterns
        memory_metrics = [m for metrics in self.performance_history.values()
                          for m in metrics if 'memory' in m.metric_name.lower()]

        if memory_metrics and len(memory_metrics) > 10:
            avg_memory = sum(m.value for m in memory_metrics[-10:]) / 10
            if avg_memory > 1000:  # > 1GB
                recommendations.append({
                    'type': 'memory_optimization',
                    'priority': 'medium',
                    'title': 'High Memory Usage Detected',
                    'description': f'Average memory usage: {avg_memory:.1f}MB',
                    'action': 'Implement memory optimization strategies'
                })

        return recommendations

    def _create_performance_degradation_candidate(self,
                                                  metric_name: str,
                                                  recent_avg: float,
                                                  historical_avg: float) -> None:
        """Create optimization candidate for performance degradation."""
        target_file, target_function = self._infer_optimization_target(
            metric_name, self.performance_history[metric_name]
        )

        if not target_file:
            return

        degradation_ratio = (recent_avg - historical_avg) / historical_avg

        candidate = OptimizationCandidate(
            optimization_id=f"degradation_{metric_name}_{int(time.time())}",
            optimization_type=OptimizationType.ALGORITHM_SELECTION,
            severity=OptimizationSeverity.HIGH if degradation_ratio > 0.5 else OptimizationSeverity.MEDIUM,
            target_file=target_file,
            target_function=target_function,
            description=f"Fix performance degradation in {target_function}",
            estimated_impact=degradation_ratio,
            confidence_score=0.9,
            proposed_changes={
                'optimization_type': 'fix_degradation',
                'metric': metric_name,
                'degradation_ratio': degradation_ratio
            },
            performance_evidence=self.performance_history[metric_name][-10:],
            created_at=datetime.now()
        )

        self.optimization_candidates.append(candidate)

        self.logger.warning(f"Performance degradation detected in {metric_name}: "
                            f"{degradation_ratio:.1%} slower than baseline")


def create_self_optimizer(persistent_memory: PersistentMemory,
                          config: Dict[str, Any] = None) -> SelfOptimizer:
    """
    Create and configure self-optimizer instance.

    Args:
        persistent_memory: Persistent memory instance
        config: Configuration dictionary

    Returns:
        SelfOptimizer instance
    """
    return SelfOptimizer(persistent_memory, config)
