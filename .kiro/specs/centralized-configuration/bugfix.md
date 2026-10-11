# Bugfix Requirements Document

## Introduction

The NEPSE quantitative trading system suffers from scattered configuration management across 40+ files, making the codebase difficult to maintain, prone to inconsistencies, and impossible to reconfigure without multi-file edits. Critical configuration values (base directory paths, trading session times, NPT timezone offset, broker ID mappings) are hardcoded inline or computed redundantly in each module that needs them. This architectural debt prevents atomic configuration changes and increases the risk of introducing inconsistencies when system parameters need to be updated.

This bug fix introduces a centralized configuration module that provides a single source of truth for all system-wide constants, computed paths, and environment-dependent values.

## Bug Analysis

### Current Behavior (Defect)

**Section 1: Path Resolution**

1.1 WHEN a module needs the base directory path THEN the system computes `Path(__file__).resolve().parents[N]` where N varies between 1, 2, and 3 depending on module depth, causing inconsistent base path resolution across ~40 files

1.2 WHEN different modules compute BASE_DIR independently THEN the system creates potential path mismatches if file structure changes or modules are relocated

1.3 WHEN BASE_DIR is needed in a module THEN the system repeats the path computation logic instead of referencing a single canonical source

**Section 2: Trading Session Constants**

2.1 WHEN trading hours need to be referenced THEN the system uses hardcoded values scattered across multiple files without a single source of truth (pre-open: 10:30-11:00, continuous: 11:00-15:00)

2.2 WHEN trading session times change THEN the system requires grep-and-replace across dozens of files to update all occurrences

**Section 3: Timezone Handling**

3.1 WHEN NPT timezone offset is needed THEN the system computes `timedelta(hours=5, minutes=45)` inline in 3+ files instead of using a shared constant

3.2 WHEN timezone-aware operations are performed THEN the system recreates the NPT timezone offset redundantly, risking calculation errors or inconsistencies

**Section 4: Broker Metadata**

4.1 WHEN broker ID mappings are needed THEN the system scatters broker metadata across ingestion files without a centralized broker registry

4.2 WHEN broker information needs to be updated THEN the system requires manual edits in multiple disconnected locations

**Section 5: Database Paths**

5.1 WHEN database file paths are constructed THEN the system builds paths ad-hoc in each module using string concatenation or Path joins with no validation

5.2 WHEN a database file location needs to change THEN the system requires tracking down all path construction sites manually

**Section 6: Environment Variables**

6.1 WHEN environment-dependent configuration is accessed THEN the system uses `os.environ.get()` or `os.getenv()` inconsistently across 16 files without centralized defaults or validation

6.2 WHEN an environment variable is missing THEN the system may use inconsistent fallback values or fail silently depending on the module

### Expected Behavior (Correct)

**Section 2: Path Resolution**

2.1 WHEN a module needs the base directory path THEN the system SHALL provide a single canonical `BASE_DIR` constant from a centralized configuration module

2.2 WHEN BASE_DIR is accessed from any module THEN the system SHALL return the same absolute path computed once at application startup

2.3 WHEN file structure changes THEN the system SHALL require updating path resolution logic in only one location (the configuration module)

**Section 3: Trading Session Constants**

3.1 WHEN trading hours need to be referenced THEN the system SHALL provide named constants (e.g., `PRE_OPEN_START`, `PRE_OPEN_END`, `CONTINUOUS_START`, `CONTINUOUS_END`) from the configuration module

3.2 WHEN trading session times change THEN the system SHALL require updating only the centralized configuration constants

**Section 4: Timezone Handling**

4.1 WHEN NPT timezone offset is needed THEN the system SHALL provide a single `NPT_TIMEZONE` constant computed once in the configuration module

4.2 WHEN timezone-aware operations are performed THEN the system SHALL reference the shared NPT_TIMEZONE constant instead of recomputing the offset

**Section 5: Broker Metadata**

5.1 WHEN broker ID mappings are needed THEN the system SHALL provide a centralized broker registry (dictionary or dataclass) in the configuration module

5.2 WHEN broker information needs to be updated THEN the system SHALL require changes only to the centralized broker registry

**Section 6: Database Paths**

6.1 WHEN database file paths are constructed THEN the system SHALL provide pre-validated path constants (e.g., `DUCKDB_LAKEHOUSE_PATH`, `SQLITE_CACHE_PATH`) from the configuration module

6.2 WHEN a database file location needs to change THEN the system SHALL require updating only the centralized path configuration

**Section 7: Environment Variables**

7.1 WHEN environment-dependent configuration is accessed THEN the system SHALL load all environment variables through a centralized settings module with explicit defaults

7.2 WHEN an environment variable is missing THEN the system SHALL use the centralized default value consistently across all modules

### Unchanged Behavior (Regression Prevention)

**Section 3: Existing Functionality**

3.1 WHEN modules access configuration values after refactoring THEN the system SHALL CONTINUE TO return the same effective values as before (same paths, same trading hours, same timezone offset)

3.2 WHEN database operations execute THEN the system SHALL CONTINUE TO access the same database file paths as before the refactoring

3.3 WHEN time-based operations execute THEN the system SHALL CONTINUE TO use the same NPT timezone offset (+05:45) as before

3.4 WHEN ingestion processes run THEN the system SHALL CONTINUE TO use the same broker ID mappings as before

3.5 WHEN environment variables are accessed THEN the system SHALL CONTINUE TO respect environment variable overrides (centralized defaults should be fallbacks, not replacements)

3.6 WHEN modules import the configuration THEN the system SHALL CONTINUE TO initialize successfully without circular import errors

3.7 WHEN the application runs on the existing machine THEN the system SHALL CONTINUE TO resolve paths correctly to `c:\Users\achar\Downloads\neps` when no environment override is provided
