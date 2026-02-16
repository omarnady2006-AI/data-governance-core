import pandas as pd
import sys
import argparse
from .pipeline import Pipeline
from .batch_processor import BatchProcessor

def main():
    parser = argparse.ArgumentParser(description="Leakage Auto-Supervisor Agent")
    subparsers = parser.add_subparsers(dest="command")
    
    # Existing run command
    run_parser = subparsers.add_parser("run", help="Process a single CSV file")
    run_parser.add_argument("--input", required=True, help="Input CSV file")
    run_parser.add_argument("--policy", default="policy/versions/v1", help="Policy directory")
    run_parser.add_argument("--out", default="outputs", help="Output directory")
    run_parser.add_argument("--copy-id", default="default", help="Copy ID")
    
    # NEW: Batch command
    batch_parser = subparsers.add_parser("batch", help="Process multiple CSV files")
    batch_parser.add_argument("--input-dir", required=True, help="Input directory with CSV files")
    batch_parser.add_argument("--policy", default="policy/versions/v1", help="Policy directory")
    batch_parser.add_argument("--out", default="outputs", help="Output directory")
    batch_parser.add_argument("--pattern", default="*.csv", help="File pattern (default: *.csv)")
    batch_parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    batch_parser.add_argument("--quiet", action="store_true", help="Suppress progress bar")
    
    args = parser.parse_args()
    
    if args.command == "run":
        try:
            df = pd.read_csv(args.input)
            pipeline = Pipeline(policy_dir=args.policy)
            _, report = pipeline.run(df, out_dir=args.out, copy_id=args.copy_id)
            
            print(f"Decision: {report['decision']}")
            print(f"Reason Codes: {', '.join(report['reason_codes'])}")
            
            if report["decision"] == "ACCEPT":
                sys.exit(0)
            elif report["decision"] == "REJECT":
                sys.exit(2)
            elif report["decision"] == "QUARANTINE":
                sys.exit(3)
        except Exception as e:
            print(f"Runtime Error: {e}")
            sys.exit(1)
    
    elif args.command == "batch":
        try:
            pipeline = Pipeline(policy_dir=args.policy)
            processor = BatchProcessor(
                pipeline=pipeline,
                max_workers=args.workers,
                verbose=not args.quiet
            )
            
            summary = processor.process_directory(
                input_dir=args.input_dir,
                out_dir=args.out,
                pattern=args.pattern
            )
            
            if summary['total'] > 0:
                print("\n" + "=" * 60)
                print("BATCH PROCESSING SUMMARY")
                print("=" * 60)
                print(f"Total files:    {summary['total']}")
                print(f"✅ Accepted:    {summary['accepted']} ({summary['accepted']/summary['total']*100:.1f}%)")
                print(f"❌ Rejected:    {summary['rejected']} ({summary['rejected']/summary['total']*100:.1f}%)")
                print(f"⚠️  Quarantined: {summary['quarantined']} ({summary['quarantined']/summary['total']*100:.1f}%)")
                print(f"💥 Failed:      {summary['failed']}")
                print("=" * 60)
            else:
                print("No files found matching pattern.")
            
            # Exit code based on results
            if summary['failed'] > 0:
                sys.exit(1)  # Processing errors
            elif summary['quarantined'] > 0:
                sys.exit(3)  # Security issues
            elif summary['rejected'] > 0:
                sys.exit(2)  # Quality issues
            else:
                sys.exit(0)  # All accepted
                
        except Exception as e:
            print(f"Batch Processing Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
