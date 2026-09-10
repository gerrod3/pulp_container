from django.db.models import F, Q, TextField, Value
from django.db.models.functions import Concat

from pulpcore.plugin.models import Distribution

from pulp_container.app.models import ContainerDistribution, ContainerPullThroughDistribution
from pulp_container.constants import (
    PULL_THROUGH_DISTRIBUTION_LABEL,
    PULL_THROUGH_DISTRIBUTION_LABEL_VALUE,
)

PULL_THROUGH_DISTRIBUTION_MARKER = {
    PULL_THROUGH_DISTRIBUTION_LABEL: PULL_THROUGH_DISTRIBUTION_LABEL_VALUE
}


def is_pull_through_distribution_marked(distribution):
    """Return whether a pull-through distribution uses its name as its registry path."""
    return all(
        (distribution.pulp_labels or {}).get(key) == value
        for key, value in PULL_THROUGH_DISTRIBUTION_MARKER.items()
    )


def get_pull_through_distribution_path(distribution):
    """Return the registry path represented by a pull-through distribution."""
    if is_pull_through_distribution_marked(distribution):
        return distribution.name
    return distribution.base_path


def _match_path(queryset, path, field):
    """Return the longest segment-aware path match from a queryset."""
    prefix_field = f"{field}_prefix"
    return (
        queryset.annotate(
            requested_path=Value(path, output_field=TextField()),
            **{prefix_field: Concat(F(field), Value("/"), output_field=TextField())},
        )
        .filter(Q(requested_path=F(field)) | Q(requested_path__startswith=F(prefix_field)))
        .order_by(f"-{field}")
        .first()
    )


def get_pull_through_distribution(path, domain):
    """Find a pull-through distribution using the repaired scheme, then the legacy scheme."""
    distributions = ContainerPullThroughDistribution.objects.filter(pulp_domain=domain)
    marked = distributions.filter(pulp_labels__contains=PULL_THROUGH_DISTRIBUTION_MARKER)
    if distribution := _match_path(marked, path, "name"):
        return distribution

    legacy = distributions.exclude(pulp_labels__contains=PULL_THROUGH_DISTRIBUTION_MARKER)
    return _match_path(legacy, path, "base_path")


def find_container_distribution_overlaps():
    """Return pairs where a container distribution overlaps any distribution."""
    container_ids = set(ContainerDistribution.objects.values_list("pk", flat=True))
    distributions = Distribution.objects.select_related("pulp_domain").order_by(
        "pulp_domain_id", "base_path", "pk"
    )
    by_domain_and_path = {
        (distribution.pulp_domain_id, distribution.base_path): distribution
        for distribution in distributions.iterator()
    }
    overlaps = []

    for distribution in by_domain_and_path.values():
        parts = distribution.base_path.split("/")
        for index in range(1, len(parts)):
            parent_path = "/".join(parts[:index])
            if parent := by_domain_and_path.get((distribution.pulp_domain_id, parent_path)):
                if parent.pk in container_ids or distribution.pk in container_ids:
                    overlaps.append((parent, distribution))

    return overlaps
