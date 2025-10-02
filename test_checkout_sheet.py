import argparse
import sys
import os
from datetime import datetime
import traceback
from io import StringIO
import contextlib

# Ensure access to shared utilities (Logger, sheets_update, etc.)
# Adjust this path if your environment differs
SHARED_UTILS_PATH = r"K:\10. Released Software\Shared Python Programs\production-2.1"
if SHARED_UTILS_PATH not in sys.path:
    sys.path.append(SHARED_UTILS_PATH)

try:
    from sheets_update import Checkout_Sheet
except Exception as e:
    print("Failed to import Checkout_Sheet from sheets_update. Make sure the shared path is reachable:")
    print(f"  Path attempted: {SHARED_UTILS_PATH}")
    traceback.print_exc()
    sys.exit(1)


def parse_axes(axes_arg: str):
    if not axes_arg:
        return ["ST01"]
    # Allow comma or space separated values
    parts = [p.strip() for p in axes_arg.replace(" ", ",").split(",") if p.strip()]
    # Normalize to ST## format if user passed integers like 1,2
    norm = []
    for p in parts:
        if p.upper().startswith("ST") and len(p) >= 3:
            norm.append(p.upper())
        else:
            # Try to coerce to integer station number
            try:
                i = int(p)
                norm.append(f"ST{i:02d}")
            except ValueError:
                norm.append(p)
    return norm or ["ST01"]


def build_flat_sample_data(technician, date_str, halls, marker, limits,
                     total_travel, home_marker_from_limit, home_offset,
                     abs_at_ccw_eot, abs_pos_offset, include_absolute: bool = False):
    """Builds a flat key/value map matching column A labels in the sheet.

    When include_absolute is False, omit absolute-only fields to mimic skipping
    checkout_test's absolute section.
    """
    data = {
        "Testing Technician": technician,
        "Date of Testing": date_str,
        "Halls": halls,
        "Marker": marker,
        "Limits": limits,
        "Total Travel": total_travel,
        "Home Marker from Limit": home_marker_from_limit,
        "Home Offset": home_offset,
    }
    if include_absolute:
        # Keep legacy misspelling only for flat mode if needed
        data["Absolute value at CCW EOT"] = abs_at_ccw_eot
        data["Absoloute Position Offset"] = abs_pos_offset
    return data

def build_nested_sample_data(axes, technician, date_str, halls, marker, limits,
                     total_travel, home_marker_from_limit, home_offset,
                     abs_at_ccw_eot, abs_pos_offset, include_absolute: bool = False):
    """Builds a nested per-axis dict mirroring checkout_test.py usage.

    Keys match those used in checkout_test. When include_absolute is False,
    omit absolute-only fields to mimic skipping checkout_test's absolute section.
    """
    nested = {}
    for axis in axes:
        per_axis = {
            "Testing Technician": technician,
            "Date of Testing": date_str,
            "Halls": halls,
            "Marker": marker,
            "Limits": limits,
            "Total Travel": total_travel,
            "Home Marker from Limit": home_marker_from_limit,
            "Home Offset": home_offset,
        }
        if include_absolute:
            per_axis["Absolute value at CCW EOT"] = abs_at_ccw_eot
            # Note: Correct spelling here to match checkout_test.py
            per_axis["Absolute Position Offset"] = abs_pos_offset
        nested[axis] = per_axis
    return nested


def run_checkout(job, data, fail_on_log_error=False, error_pattern="Error processing response"):
    """Run Checkout_Sheet while capturing its stdout/stderr.

    If fail_on_log_error is True, raise RuntimeError when error_pattern
    appears in captured output.
    """
    buf_out = StringIO()
    buf_err = StringIO()
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            checkout_sheet = Checkout_Sheet(job, data)
            checkout_sheet.duplicate_sheet()
            checkout_sheet.populate_sheet()
    except Exception:
        print("--- Captured stdout from Checkout_Sheet ---")
        print(buf_out.getvalue())
        print("--- Captured stderr from Checkout_Sheet ---")
        print(buf_err.getvalue())
        raise
    else:
        out = buf_out.getvalue()
        err = buf_err.getvalue()
        if out.strip():
            print("--- Captured stdout from Checkout_Sheet ---")
            print(out)
        if err.strip():
            print("--- Captured stderr from Checkout_Sheet ---")
            print(err)
        if fail_on_log_error and (error_pattern in out or error_pattern in err):
            raise RuntimeError(f"Detected log error pattern '{error_pattern}' in Checkout_Sheet output")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Standalone tester for Checkout_Sheet. Can build data in a nested, per-axis structure "
            "to mirror checkout_test.py without running BurnIn."
        )
    )
    parser.add_argument("--job", required=True, help="Job/serial number to pass to Checkout_Sheet")
    parser.add_argument("--axes", default="ST01", help="Comma/space-separated list of axes (e.g., 'ST01,ST02' or '1 2')")
    parser.add_argument("--technician", default=os.environ.get("USERNAME", "Tester"), help="Testing Technician name")
    parser.add_argument("--date", default=None, help="Date of Testing (default: now, '%Y-%m-%d %H:%M:%S')")

    # Measurement-ish fields (strings or numbers accepted by the downstream sheet logic)
    parser.add_argument("--halls", default="OK", help="Halls field value")
    parser.add_argument("--marker", default="OK", help="Marker field value")
    parser.add_argument("--limits", default="Pass", help="Limits field value")
    parser.add_argument("--total-travel", type=float, default=100.0, help="Total Travel value")
    parser.add_argument("--home-marker-from-limit", type=float, default=5.0, help="Home Marker from Limit value")
    parser.add_argument("--home-offset", type=float, default=0.0, help="Home Offset value")
    parser.add_argument("--abs-ccw", type=float, default=0.0, help="Absolute value at CCW EOT")
    parser.add_argument("--abs-offset", type=float, default=0.0, help="Absolute Position Offset")

    parser.add_argument("--print-only", action="store_true", help="Print the payload but do not call Google Sheets")
    parser.add_argument("--fail-on-log-error", action="store_true", help="Fail if Checkout_Sheet prints a known error line (e.g., 'Error processing response')")
    parser.add_argument("--log-error-pattern", default="Error processing response", help="Substring to detect in captured output that should trigger failure when --fail-on-log-error is set")
    parser.add_argument("--structure", choices=["nested", "flat"], default="nested", help="Data layout: 'nested' mirrors checkout_test.py; 'flat' is a single map")
    parser.add_argument("--absolute", action="store_true", help="Include absolute-branch fields (default: skip absolute section)")

    args = parser.parse_args()

    axes = parse_axes(args.axes)
    date_str = args.date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    include_absolute = bool(args.absolute)
    if args.structure == "nested":
        data = build_nested_sample_data(
            axes=axes,
            technician=args.technician,
            date_str=date_str,
            halls=args.halls,
            marker=args.marker,
            limits=args.limits,
            total_travel=args.total_travel,
            home_marker_from_limit=args.home_marker_from_limit,
            home_offset=args.home_offset,
            abs_at_ccw_eot=args.abs_ccw,
            abs_pos_offset=args.abs_offset,
            include_absolute=include_absolute,
        )
    else:
        data = build_flat_sample_data(
            technician=args.technician,
            date_str=date_str,
            halls=args.halls,
            marker=args.marker,
            limits=args.limits,
            total_travel=args.total_travel,
            home_marker_from_limit=args.home_marker_from_limit,
            home_offset=args.home_offset,
            abs_at_ccw_eot=args.abs_ccw,
            abs_pos_offset=args.abs_offset,
            include_absolute=include_absolute,
        )

    print("--- Test Payload ---")
    print(f"Job: {args.job}")
    print(f"Axes: {axes}")
    print(f"Structure: {args.structure}")
    print(f"Absolute mode: {args.absolute}")
    print(f"Data: {data}")

    if args.print_only:
        print("--print-only specified; exiting before calling Checkout_Sheet.")
        return

    try:
        # Mirror the callsite with captured output
        run_checkout(
            job=args.job,
            data=data,
            fail_on_log_error=args.fail_on_log_error,
            error_pattern=args.log_error_pattern,
        )
        print("Checkout_Sheet operations completed successfully.")
    except Exception as e:
        print("ERROR while executing Checkout_Sheet calls:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
