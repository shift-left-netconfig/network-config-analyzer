import json
from csv import DictWriter, DictReader
from pathlib import Path

from benchmarking.analyze_profile_results import get_function_profiles
from benchmarking.utils import get_experiment_results_dir, Benchmark, get_benchmark_result_file, BenchmarkProcedure
from benchmarking.iter_benchmarks import iter_benchmarks

TOP_N = 40
# TODO: some benchmarks appear more then once... This is problematic, think about how to give them unique names


def _get_report_dir(experiment_name: str) -> Path:
    report_dir = get_experiment_results_dir(experiment_name) / 'reports'
    report_dir.mkdir(exist_ok=True, parents=True)
    return report_dir


def _round_all_numeric_entries(lines: list[dict]) -> list[dict]:
    new_lines = []
    for line in lines:
        new_line = {}
        for key, value in line.items():
            if isinstance(value, float):
                new_line[key] = round(value, 5)
            else:
                new_line[key] = value
        new_lines.append(new_line)
    return new_lines


def _dict_list_to_csv(lines: list[dict], path: Path):
    lines = _round_all_numeric_entries(lines)

    # Not using set for doing this in order to keep the same order. using sets messes this up.
    field_names = []
    for line in lines:
        for field_name in line.keys():
            if field_name not in field_names:
                field_names.append(field_name)

    with path.open('w', newline='') as f:
        writer = DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(lines)


def _extract_report_data_from_audit_result(audit_result: list) -> dict:
    # TODO: change this when this becomes more complicated
    return audit_result[0][0]


def create_report_per_benchmark(experiment_name: str, benchmark: Benchmark):
    report_dir = _get_report_dir(experiment_name)
    top_func_records = get_function_profiles(experiment_name, [benchmark])[:TOP_N]
    top_func_report_path = report_dir / f'{benchmark.name}_top_func_report.csv'
    _dict_list_to_csv(top_func_records, top_func_report_path)


def create_report(experiment_name: str, benchmark_list: list[Benchmark]):
    """Creates the report for the experiment, after running all the benchmarking procedures"""
    lines = []
    report_dir = _get_report_dir(experiment_name)

    for benchmark in benchmark_list:
        line = {
            'name': benchmark.name,
            'query_type': benchmark.query_type,
            'original_scheme_file': str(benchmark.original_scheme_file_relative_to_repo),
            'query_name': benchmark.query_name
        }

        timing_results_path = get_benchmark_result_file(benchmark, experiment_name, BenchmarkProcedure.TIME)
        with timing_results_path.open('r') as f:
            timing_results = json.load(f)
            line.update(timing_results)

        auditing_results_path = get_benchmark_result_file(benchmark, experiment_name, BenchmarkProcedure.AUDIT)
        with auditing_results_path.open('r') as f:
            auditing_results = json.load(f)

        audit_data = _extract_report_data_from_audit_result(auditing_results)
        line.update(audit_data)

        lines.append(line)

    top_func_records = get_function_profiles(experiment_name, benchmark_list)[:TOP_N]
    top_func_report_path = report_dir / f'accumulated_top_func_report.csv'
    _dict_list_to_csv(top_func_records, top_func_report_path)

    timing_report_path = report_dir / 'timing_report.csv'
    _dict_list_to_csv(lines, timing_report_path)


def _benchmark_processed(experiment_name: str, benchmark: Benchmark) -> bool:
    for benchmark_procedure in [BenchmarkProcedure.TIME, BenchmarkProcedure.PROFILE, BenchmarkProcedure.AUDIT]:
        result_file = get_benchmark_result_file(benchmark, experiment_name, benchmark_procedure)
        if not result_file.exists():
            return False
    return True


def create_report_for_unfinished_benchmarking():
    experiment_name = 'remote_07-09-2022'
    # experiment_name = 'test'
    processed_benchmarks_list = [benchmark for benchmark in iter_benchmarks() if
                                 _benchmark_processed(experiment_name, benchmark)]
    create_report(experiment_name, processed_benchmarks_list)


def add_original_scheme_file_and_query_name_to_report():
    experiment_name = 'remote_07-09-2022'
    timing_report_file = _get_report_dir(experiment_name) / 'timing_report.csv'
    new_timing_report_file = timing_report_file.with_stem('timing_report_new')

    with timing_report_file.open('r') as f:
        reader = DictReader(f)
        lines = [d for d in reader]

    benchmark_list = list(iter_benchmarks())
    # TODO: I think that we can assume that the two lists are aligned, and not loop them both (what is missing was just
    #  not executed
    not_aligned_count = 0
    for i, (benchmark, line) in enumerate(zip(benchmark_list, lines)):
        if line['name'] == benchmark.name:
            line['original_scheme_file'] = str(benchmark.original_scheme_file_relative_to_repo)
            line['query_name'] = benchmark.query_name
        else:
            print(f'{i} NOT ALIGNED')
            not_aligned_count += 1

    _dict_list_to_csv(lines, new_timing_report_file)
    print(f'{not_aligned_count} are not aligned out of {min(len(benchmark_list),len(lines))}')


# TODO: check how many benchmarks there are and how much unique names
def count_unique_benchmark_names():
    benchmark_list = list(iter_benchmarks())
    unique_names = {benchmark.name for benchmark in benchmark_list}
    print(f'n_unique_names={len(unique_names)}, n_benchmarks={len(benchmark_list)}')


if __name__ == '__main__':
    # create_report_for_unfinished_benchmarking()
    add_original_scheme_file_and_query_name_to_report()
    # count_unique_benchmark_names()