from datetime import datetime

def generate_report(copy_id, decision, reason_codes, metrics, postcheck_results, forbidden_info, transform_summary):
    return {
        "copy_id": copy_id,
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "reason_codes": reason_codes,
        "metrics": metrics,
        "postcheck_summary": {
            "postcheck_ok": postcheck_results["postcheck_ok"],
            "patterns_remaining_count": postcheck_results["patterns_remaining_count"],
            "hits": postcheck_results["pattern_hits"]
        },
        "forbidden_summary": forbidden_info,
        "transform_summary": transform_summary
    }
