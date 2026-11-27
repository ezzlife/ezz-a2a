"""Known defect patterns that the coordinator checks without calling any model."""

from ezz_a2a.review.lessons import like_without_escape, order_by_without_tiebreaker, path_from_argv

LESSONS = (like_without_escape, order_by_without_tiebreaker, path_from_argv)


def find_hits(sources: list[dict]) -> list[dict]:
    return [{"lesson": lesson.ID, "path": source["path"], "line": line, "note": lesson.NOTE}
            for source in sources for lesson in LESSONS for line in lesson.check(source)]
