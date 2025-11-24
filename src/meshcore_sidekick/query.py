"""Database query tool for viewing captured MeshCore data."""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import sqlite3
except ImportError:
    print("Error: sqlite3 module not available", file=sys.stderr)
    sys.exit(1)


class DatabaseQuery:
    """Query tool for MeshCore database."""

    def __init__(self, db_path: str):
        """
        Initialize database query tool.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def print_summary(self):
        """Print database summary statistics."""
        print("=" * 80)
        print("MESHCORE DATABASE SUMMARY")
        print("=" * 80)
        print(f"\nDatabase: {self.db_path}")

        # Database size
        db_size = Path(self.db_path).stat().st_size
        print(f"Size: {db_size:,} bytes ({db_size / 1024:.1f} KB)")

        print("\n" + "-" * 80)
        print("TABLE STATISTICS")
        print("-" * 80)

        tables = [
            ("events_log", "All Events"),
            ("nodes", "Nodes"),
            ("messages", "Messages"),
            ("advertisements", "Advertisements"),
            ("paths", "Routing Paths"),
            ("trace_paths", "Trace Paths"),
            ("telemetry", "Telemetry"),
            ("acknowledgments", "Acknowledgments"),
            ("status_responses", "Status Responses"),
            ("statistics", "Statistics"),
            ("binary_responses", "Binary Responses"),
            ("control_data", "Control Data"),
            ("raw_data", "Raw Data"),
            ("device_info", "Device Info"),
        ]

        for table, description in tables:
            try:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                print(f"  {description:.<30} {count:>8,}")
            except sqlite3.Error as e:
                print(f"  {description:.<30} ERROR: {e}")

    def print_event_breakdown(self):
        """Print breakdown of events by type."""
        print("\n" + "-" * 80)
        print("EVENT TYPE BREAKDOWN")
        print("-" * 80)

        self.cursor.execute(
            "SELECT event_type, COUNT(*) as count FROM events_log "
            "GROUP BY event_type ORDER BY count DESC"
        )
        results = self.cursor.fetchall()

        if results:
            for event_type, count in results:
                print(f"  {event_type:.<40} {count:>8,}")
        else:
            print("  No events recorded")

    def print_recent_events(self, limit: int = 10):
        """Print recent events."""
        print("\n" + "-" * 80)
        print(f"RECENT EVENTS (last {limit})")
        print("-" * 80)

        self.cursor.execute(
            "SELECT event_type, created_at FROM events_log "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        results = self.cursor.fetchall()

        if results:
            for event_type, created_at in results:
                print(f"  [{created_at}] {event_type}")
        else:
            print("  No events recorded")

    def print_nodes(self, limit: int = 10):
        """Print discovered nodes."""
        print("\n" + "-" * 80)
        print(f"NODES (showing up to {limit})")
        print("-" * 80)

        self.cursor.execute(
            "SELECT name, public_key_prefix_8, node_type, last_seen, first_seen "
            "FROM nodes ORDER BY last_seen DESC LIMIT ?",
            (limit,)
        )
        results = self.cursor.fetchall()

        if results:
            for name, prefix, node_type, last_seen, first_seen in results:
                name_display = name or "Unknown"
                type_display = node_type or "unknown"
                print(f"\n  Node: {name_display}")
                print(f"    Public Key: {prefix}...")
                print(f"    Type: {type_display}")
                print(f"    First Seen: {first_seen}")
                print(f"    Last Seen: {last_seen}")
        else:
            print("  No nodes discovered")

    def print_messages(self, limit: int = 10):
        """Print recent messages."""
        print("\n" + "-" * 80)
        print(f"MESSAGES (last {limit})")
        print("-" * 80)

        self.cursor.execute(
            "SELECT direction, message_type, from_public_key, to_public_key, "
            "content, snr, rssi, timestamp, received_at "
            "FROM messages ORDER BY received_at DESC LIMIT ?",
            (limit,)
        )
        results = self.cursor.fetchall()

        if results:
            for idx, (direction, msg_type, from_key, to_key, content, snr, rssi, ts, recv) in enumerate(results, 1):
                print(f"\n  Message #{idx}")
                print(f"    Direction: {direction}")
                print(f"    Type: {msg_type}")
                print(f"    From: {from_key[:16] if from_key else 'Unknown'}...")
                if to_key:
                    print(f"    To: {to_key[:16]}...")
                print(f"    Content: {content[:100]}")
                if snr is not None:
                    print(f"    SNR: {snr:.1f} dB")
                if rssi is not None:
                    print(f"    RSSI: {rssi:.1f} dBm")
                print(f"    Timestamp: {ts}")
                print(f"    Received: {recv}")
        else:
            print("  No messages recorded")

    def print_advertisements(self, limit: int = 10):
        """Print recent advertisements."""
        print("\n" + "-" * 80)
        print(f"ADVERTISEMENTS (last {limit})")
        print("-" * 80)

        self.cursor.execute(
            "SELECT public_key, adv_type, name, latitude, longitude, received_at "
            "FROM advertisements ORDER BY received_at DESC LIMIT ?",
            (limit,)
        )
        results = self.cursor.fetchall()

        if results:
            for idx, (pub_key, adv_type, name, lat, lon, recv) in enumerate(results, 1):
                print(f"\n  Advertisement #{idx}")
                print(f"    Public Key: {pub_key[:16]}...")
                print(f"    Type: {adv_type or 'unknown'}")
                print(f"    Name: {name or 'Unknown'}")
                if lat is not None and lon is not None:
                    print(f"    Location: {lat:.4f}, {lon:.4f}")
                print(f"    Received: {recv}")
        else:
            print("  No advertisements recorded")

    def print_telemetry(self, limit: int = 5):
        """Print recent telemetry data."""
        print("\n" + "-" * 80)
        print(f"TELEMETRY (last {limit})")
        print("-" * 80)

        self.cursor.execute(
            "SELECT node_public_key, parsed_data, received_at "
            "FROM telemetry ORDER BY received_at DESC LIMIT ?",
            (limit,)
        )
        results = self.cursor.fetchall()

        if results:
            for idx, (node_key, parsed, recv) in enumerate(results, 1):
                print(f"\n  Telemetry #{idx}")
                print(f"    Node: {node_key}...")
                print(f"    Received: {recv}")
                if parsed:
                    try:
                        data = json.loads(parsed)
                        print(f"    Data:")
                        for key, value in data.items():
                            print(f"      {key}: {value}")
                    except json.JSONDecodeError:
                        print(f"    Data: {parsed}")
        else:
            print("  No telemetry recorded")

    def print_trace_paths(self, limit: int = 5):
        """Print recent trace paths."""
        print("\n" + "-" * 80)
        print(f"TRACE PATHS (last {limit})")
        print("-" * 80)

        self.cursor.execute(
            "SELECT initiator_tag, destination_public_key, path_hashes, "
            "snr_values, hop_count, completed_at "
            "FROM trace_paths ORDER BY completed_at DESC LIMIT ?",
            (limit,)
        )
        results = self.cursor.fetchall()

        if results:
            for idx, (tag, dest, hashes, snrs, hops, completed) in enumerate(results, 1):
                print(f"\n  Trace Path #{idx}")
                print(f"    Initiator Tag: 0x{tag:08x}")
                if dest:
                    print(f"    Destination: {dest[:16]}...")
                print(f"    Hop Count: {hops or 'N/A'}")
                print(f"    Completed: {completed}")
                if hashes:
                    try:
                        path = json.loads(hashes)
                        print(f"    Path: {' -> '.join(path)}")
                    except json.JSONDecodeError:
                        pass
                if snrs:
                    try:
                        snr_list = json.loads(snrs)
                        print(f"    SNR values: {', '.join(f'{s:.1f}' for s in snr_list)}")
                    except json.JSONDecodeError:
                        pass
        else:
            print("  No trace paths recorded")

    def print_activity_timeline(self, hours: int = 24):
        """Print activity timeline."""
        print("\n" + "-" * 80)
        print(f"ACTIVITY TIMELINE (last {hours} hours)")
        print("-" * 80)

        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute(
            "SELECT event_type, COUNT(*) as count "
            "FROM events_log WHERE created_at >= ? "
            "GROUP BY event_type ORDER BY count DESC",
            (cutoff_str,)
        )
        results = self.cursor.fetchall()

        if results:
            total = sum(count for _, count in results)
            print(f"\n  Total events: {total:,}")
            print(f"  Since: {cutoff_str}")
            print("\n  Breakdown:")
            for event_type, count in results:
                pct = (count / total) * 100
                print(f"    {event_type:.<40} {count:>6,} ({pct:>5.1f}%)")
        else:
            print(f"  No activity in the last {hours} hours")

    def print_full_report(self):
        """Print full database report."""
        self.print_summary()
        self.print_event_breakdown()
        self.print_activity_timeline()
        self.print_recent_events()
        self.print_nodes()
        self.print_messages()
        self.print_advertisements()
        self.print_telemetry()
        self.print_trace_paths()
        print("\n" + "=" * 80)


def main():
    """Main entry point for query tool."""
    parser = argparse.ArgumentParser(
        description="Query MeshCore Sidekick database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full report
  python -m meshcore_sidekick.query

  # Summary only
  python -m meshcore_sidekick.query --summary

  # Recent messages
  python -m meshcore_sidekick.query --messages 20

  # Nodes discovered
  python -m meshcore_sidekick.query --nodes

  # Activity in last 6 hours
  python -m meshcore_sidekick.query --activity 6
        """
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default="./meshcore.db",
        help="Path to database file (default: ./meshcore.db)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics only"
    )
    parser.add_argument(
        "--events",
        type=int,
        metavar="N",
        help="Show N recent events"
    )
    parser.add_argument(
        "--nodes",
        type=int,
        metavar="N",
        nargs="?",
        const=10,
        help="Show N discovered nodes (default: 10)"
    )
    parser.add_argument(
        "--messages",
        type=int,
        metavar="N",
        nargs="?",
        const=10,
        help="Show N recent messages (default: 10)"
    )
    parser.add_argument(
        "--advertisements",
        type=int,
        metavar="N",
        nargs="?",
        const=10,
        help="Show N recent advertisements (default: 10)"
    )
    parser.add_argument(
        "--telemetry",
        type=int,
        metavar="N",
        nargs="?",
        const=5,
        help="Show N recent telemetry entries (default: 5)"
    )
    parser.add_argument(
        "--traces",
        type=int,
        metavar="N",
        nargs="?",
        const=5,
        help="Show N recent trace paths (default: 5)"
    )
    parser.add_argument(
        "--activity",
        type=int,
        metavar="HOURS",
        nargs="?",
        const=24,
        help="Show activity timeline for last N hours (default: 24)"
    )

    args = parser.parse_args()

    try:
        db = DatabaseQuery(args.db_path)

        # If no specific options, show full report
        if not any([
            args.summary,
            args.events,
            args.nodes is not None,
            args.messages is not None,
            args.advertisements is not None,
            args.telemetry is not None,
            args.traces is not None,
            args.activity is not None,
        ]):
            db.print_full_report()
        else:
            # Show requested sections
            if args.summary or any([args.events, args.nodes, args.messages, args.advertisements]):
                db.print_summary()

            if args.events:
                db.print_recent_events(args.events)

            if args.nodes is not None:
                db.print_nodes(args.nodes)

            if args.messages is not None:
                db.print_messages(args.messages)

            if args.advertisements is not None:
                db.print_advertisements(args.advertisements)

            if args.telemetry is not None:
                db.print_telemetry(args.telemetry)

            if args.traces is not None:
                db.print_trace_paths(args.traces)

            if args.activity is not None:
                db.print_activity_timeline(args.activity)

            print()  # Final newline

        db.close()

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
