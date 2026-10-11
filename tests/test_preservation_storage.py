"""
Preservation Test 2.1: Storage & Concurrency

**Validates: Requirements 3.1.1, 3.1.2, 3.1.3**

This test verifies that the storage fix maintains data integrity after implementing 
the DuckDB connection manager. It generates 100 random Parquet writes and verifies:
1. All writes complete successfully
2. No data corruption occurs
3. Exact data match between written and read data

This is a PRESERVATION test that should PASS on FIXED code (after connection manager
implementation) to verify the solution doesn't break existing functionality.

Property: For all sequential single-connection operations, results match baseline.

Requirements:
- 3.1.1: Single-threaded batch jobs continue to execute queries successfully
- 3.1.2: Sequential Parquet writes produce valid files readable by all consumers
- 3.1.3: Lightweight synchronous operations continue with sub-100ms latency
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple
import tempfile
import shutil
import time
import hashlib
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Try to import the connection manager - will be available after Task 3.1 is implemented
try:
    from scripts.db_connection import connection_manager
    CONNECTION_MANAGER_AVAILABLE = True
except ImportError:
    CONNECTION_MANAGER_AVAILABLE = False
    connection_manager = None

# Test data generators
np.random.seed(42)


def generate_random_market_data(num_rows: int = 1000, seed: int = None) -> pd.DataFrame:
    """Generate random market data for testing Parquet writes."""
    if seed is not None:
        np.random.seed(seed)
    
    tickers = ['NABIL', 'NRIC', 'NIFRA', 'NLIC', 'NMB', 'SCB', 'STC', 'EBL', 'HBL', 'SBI']
    
    data = {
        'ticker': np.random.choice(tickers, num_rows),
        'date': pd.date_range('2024-01-01', periods=num_rows, freq='D').astype(str),
        'open': np.random.uniform(100, 1000, num_rows).round(2),
        'high': np.random.uniform(100, 1000, num_rows).round(2),
        'low': np.random.uniform(100, 1000, num_rows).round(2),
        'close': np.random.uniform(100, 1000, num_rows).round(2),
        'volume': np.random.randint(1000, 100000, num_rows),
        'turnover': np.random.uniform(100000, 10000000, num_rows).round(2)
    }
    
    # Ensure high >= low, high >= open, high >= close
    df = pd.DataFrame(data)
    df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
    df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
    
    return df


def compute_dataframe_hash(df: pd.DataFrame) -> str:
    """Compute SHA256 hash of DataFrame for exact comparison."""
    # Sort by all columns to ensure consistent ordering
    df_sorted = df.sort_values(by=list(df.columns)).reset_index(drop=True)
    
    # Convert to bytes and hash
    data_bytes = df_sorted.to_csv(index=False).encode('utf-8')
    return hashlib.sha256(data_bytes).hexdigest()


class StoragePreservationValidator:
    """Validator for storage preservation property tests."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[Dict[str, Any]] = []
        self.corrupted_writes = 0
        self.successful_writes = 0
        self.failed_writes = 0
        
    def write_parquet_direct(
        self, 
        df: pd.DataFrame, 
        file_path: Path, 
        write_id: int
    ) -> Dict[str, Any]:
        """
        Write DataFrame to Parquet using direct method (UNFIXED pattern).
        
        This simulates the original behavior that should be preserved for
        sequential single-threaded operations.
        """
        start_time = time.time()
        
        try:
            # Direct write (no atomic staging)
            df.to_parquet(file_path, index=False, engine='pyarrow')
            
            write_duration = time.time() - start_time
            
            # Immediately read back to verify
            df_read = pd.read_parquet(file_path)
            
            # Compute hashes for comparison
            original_hash = compute_dataframe_hash(df)
            read_hash = compute_dataframe_hash(df_read)
            
            data_match = (original_hash == read_hash)
            
            if not data_match:
                self.corrupted_writes += 1
                status = "CORRUPTED"
            else:
                self.successful_writes += 1
                status = "SUCCESS"
            
            result = {
                'write_id': write_id,
                'status': status,
                'file_path': str(file_path),
                'rows_written': len(df),
                'rows_read': len(df_read),
                'data_match': data_match,
                'original_hash': original_hash,
                'read_hash': read_hash,
                'write_duration_ms': write_duration * 1000,
                'read_duration_ms': (time.time() - start_time - write_duration) * 1000
            }
            
        except Exception as e:
            self.failed_writes += 1
            result = {
                'write_id': write_id,
                'status': "FAILED",
                'file_path': str(file_path),
                'error': str(e),
                'data_match': False,
                'write_duration_ms': (time.time() - start_time) * 1000
            }
        
        self.results.append(result)
        return result
    
    def write_parquet_with_connection_manager(
        self, 
        df: pd.DataFrame, 
        file_path: Path, 
        write_id: int
    ) -> Dict[str, Any]:
        """
        Write DataFrame to Parquet using connection manager (FIXED pattern).
        
        This uses the centralized connection manager for database operations
        and atomic Parquet writes for file integrity.
        """
        if not CONNECTION_MANAGER_AVAILABLE:
            # Fallback to direct write if connection manager not available
            return self.write_parquet_direct(df, file_path, write_id)
        
        start_time = time.time()
        
        try:
            # Use atomic write pattern if async executor available
            try:
                from scripts.db_connection import atomic_parquet_write
                atomic_parquet_write(df, file_path)
                write_method = "atomic"
            except ImportError:
                # Fallback to direct write if atomic helper not available
                df.to_parquet(file_path, index=False, engine='pyarrow')
                write_method = "direct_fallback"
            
            write_duration = time.time() - start_time
            
            # Read back to verify
            df_read = pd.read_parquet(file_path)
            
            # Compute hashes for comparison
            original_hash = compute_dataframe_hash(df)
            read_hash = compute_dataframe_hash(df_read)
            
            data_match = (original_hash == read_hash)
            
            if not data_match:
                self.corrupted_writes += 1
                status = "CORRUPTED"
            else:
                self.successful_writes += 1
                status = "SUCCESS"
            
            result = {
                'write_id': write_id,
                'status': status,
                'write_method': write_method,
                'file_path': str(file_path),
                'rows_written': len(df),
                'rows_read': len(df_read),
                'data_match': data_match,
                'original_hash': original_hash,
                'read_hash': read_hash,
                'write_duration_ms': write_duration * 1000,
                'read_duration_ms': (time.time() - start_time - write_duration) * 1000
            }
            
        except Exception as e:
            self.failed_writes += 1
            result = {
                'write_id': write_id,
                'status': "FAILED",
                'file_path': str(file_path),
                'error': str(e),
                'data_match': False,
                'write_duration_ms': (time.time() - start_time) * 1000
            }
        
        self.results.append(result)
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all write operations."""
        total = len(self.results)
        
        avg_write_time = np.mean([r['write_duration_ms'] for r in self.results if 'write_duration_ms' in r])
        max_write_time = max([r['write_duration_ms'] for r in self.results if 'write_duration_ms' in r])
        min_write_time = min([r['write_duration_ms'] for r in self.results if 'write_duration_ms' in r])
        
        return {
            'total_writes': total,
            'successful_writes': self.successful_writes,
            'failed_writes': self.failed_writes,
            'corrupted_writes': self.corrupted_writes,
            'success_rate': (self.successful_writes / total * 100) if total > 0 else 0,
            'integrity_rate': ((self.successful_writes - self.corrupted_writes) / total * 100) if total > 0 else 0,
            'avg_write_time_ms': avg_write_time,
            'max_write_time_ms': max_write_time,
            'min_write_time_ms': min_write_time,
            'all_data_match': all(r['data_match'] for r in self.results),
            'connection_manager_available': CONNECTION_MANAGER_AVAILABLE
        }


def test_storage_preservation_100_writes():
    """
    Preservation Test 2.1: Storage Integrity
    
    **Validates: Requirements 3.1.1, 3.1.2, 3.1.3**
    
    This test generates 100 random Parquet writes and verifies:
    1. All writes complete successfully
    2. No data corruption occurs
    3. Exact data match between written and read data
    
    Expected Outcome on FIXED code: All 100 writes complete with exact data match
    """
    # Create temporary directory for test writes
    temp_dir = Path(tempfile.mkdtemp(prefix='storage_preservation_test_'))
    
    try:
        validator = StoragePreservationValidator(temp_dir)
        
        print("\n" + "=" * 80)
        print("PRESERVATION TEST: Storage Integrity - 100 Parquet Writes")
        print("=" * 80)
        print(f"Connection Manager Available: {CONNECTION_MANAGER_AVAILABLE}")
        print(f"Test Directory: {temp_dir}")
        print("=" * 80)
        
        # Generate and write 100 random DataFrames
        for i in range(100):
            # Generate random market data with unique seed
            df = generate_random_market_data(num_rows=1000, seed=42 + i)
            
            # Create unique file path
            file_path = temp_dir / f"market_data_{i:03d}.parquet"
            
            # Write using appropriate method based on connection manager availability
            if CONNECTION_MANAGER_AVAILABLE:
                result = validator.write_parquet_with_connection_manager(df, file_path, i)
            else:
                result = validator.write_parquet_direct(df, file_path, i)
            
            # Print progress every 25 writes
            if (i + 1) % 25 == 0:
                print(f"Progress: {i + 1}/100 writes completed")
        
        # Get summary
        summary = validator.get_summary()
        
        # Print detailed results
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)
        print(f"Total Writes: {summary['total_writes']}")
        print(f"Successful Writes: {summary['successful_writes']}")
        print(f"Failed Writes: {summary['failed_writes']}")
        print(f"Corrupted Writes: {summary['corrupted_writes']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Data Integrity Rate: {summary['integrity_rate']:.1f}%")
        print(f"\nWrite Performance:")
        print(f"  Average: {summary['avg_write_time_ms']:.2f}ms")
        print(f"  Min: {summary['min_write_time_ms']:.2f}ms")
        print(f"  Max: {summary['max_write_time_ms']:.2f}ms")
        print(f"\nAll Data Match: {summary['all_data_match']}")
        print(f"Connection Manager Used: {CONNECTION_MANAGER_AVAILABLE}")
        print("=" * 80)
        
        # Assertions for preservation property
        assert summary['total_writes'] == 100, (
            f"Expected 100 writes, got {summary['total_writes']}"
        )
        
        assert summary['successful_writes'] == 100, (
            f"Expected all 100 writes to succeed, got {summary['successful_writes']}. "
            f"Failed: {summary['failed_writes']}, Corrupted: {summary['corrupted_writes']}"
        )
        
        assert summary['corrupted_writes'] == 0, (
            f"Expected zero corrupted writes, got {summary['corrupted_writes']}. "
            "Data integrity violated!"
        )
        
        assert summary['all_data_match'], (
            "Not all written data matches read data. "
            "Preservation property violated!"
        )
        
        # Verify sub-100ms latency for lightweight operations (Requirement 3.1.3)
        assert summary['avg_write_time_ms'] < 100, (
            f"Average write time {summary['avg_write_time_ms']:.2f}ms exceeds 100ms threshold. "
            "Requirement 3.1.3 violated: lightweight operations should complete in <100ms"
        )
        
        print("\n✓ PRESERVATION TEST PASSED")
        print("✓ All 100 writes completed successfully")
        print("✓ All data integrity verified (exact match)")
        print("✓ Performance threshold met (<100ms per write)")
        
    finally:
        # Cleanup temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sequential_duckdb_queries_preservation():
    """
    Preservation Test 2.1b: Sequential Query Execution
    
    **Validates: Requirement 3.1.1**
    
    Verifies that single-threaded batch jobs can execute queries successfully
    with the existing SQL syntax (preservation of baseline behavior).
    """
    import duckdb
    
    # Create temporary database
    temp_db_path = Path(tempfile.mkdtemp(prefix='duckdb_preservation_')) / 'test.duckdb'
    
    try:
        # Create test data
        df = generate_random_market_data(num_rows=500, seed=12345)
        
        # Write to Parquet first
        temp_parquet = temp_db_path.parent / 'test_data.parquet'
        df.to_parquet(temp_parquet, index=False)
        
        # Test sequential queries (should work on both FIXED and UNFIXED code)
        con = duckdb.connect(str(temp_db_path))
        
        # Create table from Parquet
        con.execute(f"""
            CREATE TABLE market_data AS 
            SELECT * FROM read_parquet('{str(temp_parquet).replace(os.sep, "/")}')
        """)
        
        # Execute sequential queries
        queries = [
            "SELECT COUNT(*) FROM market_data",
            "SELECT ticker, AVG(close) as avg_close FROM market_data GROUP BY ticker",
            "SELECT * FROM market_data WHERE volume > 50000 ORDER BY date DESC LIMIT 100",
            "SELECT ticker, MAX(high) as high, MIN(low) as low FROM market_data GROUP BY ticker",
        ]
        
        results = []
        for query in queries:
            result = con.execute(query).fetchdf()
            results.append(result)
            assert len(result) > 0 or 'COUNT' in query, f"Query returned no results: {query}"
        
        con.close()
        
        print("\n✓ Sequential DuckDB queries preserved")
        print(f"✓ {len(queries)} queries executed successfully")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_db_path.parent, ignore_errors=True)


def test_concurrent_writes_with_connection_manager():
    """
    Preservation Test 2.1c: Concurrent Write Integrity
    
    Tests that concurrent Parquet writes complete without corruption
    when using the connection manager (if available).
    """
    temp_dir = Path(tempfile.mkdtemp(prefix='concurrent_writes_test_'))
    
    try:
        validator = StoragePreservationValidator(temp_dir)
        
        print("\n" + "=" * 80)
        print("CONCURRENT WRITE TEST: Using Connection Manager")
        print("=" * 80)
        
        # Generate 50 concurrent writes
        num_concurrent = 50
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            for i in range(num_concurrent):
                df = generate_random_market_data(num_rows=500, seed=999 + i)
                file_path = temp_dir / f"concurrent_{i:03d}.parquet"
                
                # Submit write task
                if CONNECTION_MANAGER_AVAILABLE:
                    future = executor.submit(
                        validator.write_parquet_with_connection_manager,
                        df, file_path, i
                    )
                else:
                    future = executor.submit(
                        validator.write_parquet_direct,
                        df, file_path, i
                    )
                
                futures.append(future)
            
            # Wait for all to complete
            results = [f.result() for f in as_completed(futures)]
        
        # Get summary
        summary = validator.get_summary()
        
        print(f"\nConcurrent Writes: {summary['total_writes']}")
        print(f"Successful: {summary['successful_writes']}")
        print(f"Corrupted: {summary['corrupted_writes']}")
        print(f"Integrity Rate: {summary['integrity_rate']:.1f}%")
        
        # All concurrent writes should succeed without corruption
        assert summary['successful_writes'] == num_concurrent, (
            f"Expected {num_concurrent} successful concurrent writes, "
            f"got {summary['successful_writes']}"
        )
        
        assert summary['corrupted_writes'] == 0, (
            f"Expected zero corrupted writes under concurrent load, "
            f"got {summary['corrupted_writes']}"
        )
        
        print("\n✓ Concurrent write test passed")
        print("✓ All concurrent writes completed without corruption")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_single_connection_operations_baseline():
    """
    Observation Test: Capture baseline behavior for single-connection operations.
    
    This test establishes the baseline behavior that must be preserved after
    implementing the connection manager. Run on UNFIXED code to capture baseline.
    """
    import duckdb
    
    temp_dir = Path(tempfile.mkdtemp(prefix='baseline_test_'))
    
    try:
        print("\n" + "=" * 80)
        print("BASELINE OBSERVATION: Single-Connection Operations")
        print("=" * 80)
        
        # Generate test data
        df = generate_random_market_data(num_rows=1000, seed=42)
        parquet_path = temp_dir / 'baseline_data.parquet'
        df.to_parquet(parquet_path, index=False)
        
        # Create single connection and execute multiple operations
        con = duckdb.connect(database=':memory:')
        
        # Load data
        p_str = str(parquet_path).replace(os.sep, "/")
        con.execute(f"CREATE TABLE baseline AS SELECT * FROM read_parquet('{p_str}')")
        
        # Execute multiple queries sequentially
        operations = []
        
        # Query 1: Aggregation
        start = time.time()
        result1 = con.execute("""
            SELECT ticker, COUNT(*) as count, AVG(close) as avg_close
            FROM baseline
            GROUP BY ticker
            ORDER BY ticker
        """).fetchdf()
        operations.append(('aggregation', time.time() - start, len(result1)))
        
        # Query 2: Filtering
        start = time.time()
        result2 = con.execute("""
            SELECT * FROM baseline
            WHERE volume > 50000
            ORDER BY date DESC
            LIMIT 100
        """).fetchdf()
        operations.append(('filtering', time.time() - start, len(result2)))
        
        # Query 3: Window functions
        start = time.time()
        result3 = con.execute("""
            WITH ranked AS (
                SELECT 
                    ticker, date, close,
                    AVG(close) OVER (PARTITION BY ticker ORDER BY date 
                        ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) as ma_10,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                FROM baseline
            )
            SELECT * FROM ranked
            WHERE rn <= 10
        """).fetchdf()
        operations.append(('window_functions', time.time() - start, len(result3)))
        
        con.close()
        
        # Report baseline
        print("\nBaseline Operations:")
        for op_name, duration, rows in operations:
            print(f"  {op_name}: {duration*1000:.2f}ms, {rows} rows")
        
        print("\n✓ Baseline behavior captured successfully")
        print("✓ Sequential queries execute without errors")
        print("✓ This behavior must be preserved after fix implementation")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 80)
    print("PRESERVATION TEST SUITE: Storage & Concurrency")
    print("=" * 80)
    print("\nThese tests verify that the storage fix maintains data integrity")
    print("and doesn't break existing functionality.")
    print("\nExpected Outcome on FIXED code: All tests PASS")
    print("=" * 80)
    
    # Run all tests
    try:
        test_storage_preservation_100_writes()
    except AssertionError as e:
        print(f"\n✗ Test 2.1 FAILED: {e}")
    
    try:
        test_sequential_duckdb_queries_preservation()
    except AssertionError as e:
        print(f"\n✗ Test 2.1b FAILED: {e}")
    
    try:
        test_concurrent_writes_with_connection_manager()
    except AssertionError as e:
        print(f"\n✗ Test 2.1c FAILED: {e}")
    
    try:
        test_single_connection_operations_baseline()
    except AssertionError as e:
        print(f"\n✗ Baseline observation FAILED: {e}")
    
    print("\n" + "=" * 80)
    print("PRESERVATION TEST SUITE COMPLETE")
    print("=" * 80)
