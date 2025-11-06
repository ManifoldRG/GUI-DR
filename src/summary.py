"""
Summary and statistics printing utilities.
"""

from typing import List, Dict, Any


def print_trajectory_summary(stats: Dict[str, Any], split: str) -> None:
    """Print overall summary for all processed trajectories."""
    print(f"\n{'#'*80}")
    print(f"📊 OVERALL SUMMARY - {split.upper()} SPLIT")
    print(f"{'#'*80}\n")
    
    print(f"Split: {split}")
    print(f"Total trajectories processed: {len(stats)}")
    print(f"\nPer-trajectory statistics:")
    print(f"{'='*80}")
    print(f"{'Task UID':<40} {'Total':<8} {'Succeeded':<10} {'Saved':<8}")
    print(f"{'-'*80}")
    
    total_steps_all = 0
    total_succeeded_all = 0
    total_saved_all = 0
    
    for stat in stats:
        task_uid = stat.get('task_uid', 'N/A')
        steps_total = stat.get('steps_total', 0)
        steps_succeeded = stat.get('steps_succeeded', 0)
        steps_saved = stat.get('steps_saved', 0)
        
        if 'error' in stat:
            print(f"{task_uid:<40} {'ERROR':<8} {'-':<10} {'-':<8}")
        else:
            print(f"{task_uid:<40} {steps_total:<8} {steps_succeeded:<10} {steps_saved:<8}")
            total_steps_all += steps_total
            total_succeeded_all += steps_succeeded
            total_saved_all += steps_saved
    
    print(f"{'-'*80}")
    print(f"{'TOTAL':<40} {total_steps_all:<8} {total_succeeded_all:<10} {total_saved_all:<8}")
    print(f"{'='*80}\n")
    
    print(f"✅ All trajectories processed!")
    print(f"📊 Total steps across all trajectories: {total_steps_all}")
    print(f"✅ Total steps succeeded: {total_succeeded_all}")
    print(f"💾 Total steps saved: {total_saved_all}")
    print(f"❌ Total steps failed/skipped: {total_steps_all - total_succeeded_all}")
    if total_steps_all > 0:
        success_rate = (total_succeeded_all / total_steps_all) * 100
        print(f"📈 Success rate: {success_rate:.2f}%")
    print(f"{'#'*80}\n")

