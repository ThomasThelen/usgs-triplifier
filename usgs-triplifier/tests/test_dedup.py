import gzip

from usgs_triplifier.lib.dataset_metadata import RETAINED_BASENAME
from usgs_triplifier.lib.dedup import remove_duplicate_triples

LINE_A = '<http://gnis-ld.org/lod/gnis/feature/1> <http://www.w3.org/2000/01/rdf-schema#label> "Blue Lake" .\n'
LINE_B = '<http://gnis-ld.org/lod/gnis/feature/2> <http://www.w3.org/2000/01/rdf-schema#label> "High Ridge" .\n'
LINE_C = '<http://gnis-ld.org/lod/gnis/feature/3> <http://www.w3.org/2000/01/rdf-schema#label> "Kept Creek" .\n'


def _write(path, lines):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.writelines(lines)


def _read(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return f.readlines()


def test_duplicates_removed_within_and_across_files(data_dirs):
    _, output_dir = data_dirs
    _write(output_dir / "features.nt.gz", [LINE_A, LINE_A, LINE_B])
    # The same triple asserted by a second dataset is also a duplicate
    _write(output_dir / "names.nt.gz", [LINE_A, LINE_C])

    removed = remove_duplicate_triples()

    assert removed == 2
    assert _read(output_dir / "features.nt.gz") == [LINE_A, LINE_B]
    # First occurrence wins: the copy in the later file is dropped
    assert _read(output_dir / "names.nt.gz") == [LINE_C]


def test_retained_records_are_left_alone(data_dirs):
    _, output_dir = data_dirs
    _write(output_dir / "features.nt.gz", [LINE_A])
    _write(output_dir / RETAINED_BASENAME, [LINE_A, LINE_A])

    removed = remove_duplicate_triples()

    assert removed == 0
    assert _read(output_dir / RETAINED_BASENAME) == [LINE_A, LINE_A]
