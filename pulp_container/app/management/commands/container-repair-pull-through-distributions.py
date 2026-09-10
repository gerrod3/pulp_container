from gettext import gettext as _
from uuid import uuid4

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from pulpcore.plugin.cache import SyncContentCache

from pulp_container.app.models import ContainerPullThroughDistribution
from pulp_container.app.pull_through import (
    PULL_THROUGH_DISTRIBUTION_MARKER,
    find_container_distribution_overlaps,
)


class Command(BaseCommand):
    """Repair pull-through distributions whose registry path is stored as their base path."""

    help = _("Repair pull-through distribution base paths and report remaining overlaps.")

    def handle(self, *args, **options):
        """Move eligible pull-through base paths and report unresolved overlaps."""
        repaired = 0
        old_base_paths = []
        distributions = ContainerPullThroughDistribution.objects.exclude(
            pulp_labels__contains=PULL_THROUGH_DISTRIBUTION_MARKER
        ).select_related("pulp_domain")

        for distribution in distributions.iterator():
            if distribution.name != distribution.base_path:
                continue

            old_base_paths.append(distribution.base_path)
            distribution.base_path = str(uuid4())
            distribution.pulp_labels = {
                **(distribution.pulp_labels or {}),
                **PULL_THROUGH_DISTRIBUTION_MARKER,
            }
            with transaction.atomic():
                distribution.save(update_fields=["base_path", "pulp_labels"])
            repaired += 1

        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} pull-through distributions."))

        unresolved = ContainerPullThroughDistribution.objects.exclude(
            pulp_labels__contains=PULL_THROUGH_DISTRIBUTION_MARKER
        ).select_related("pulp_domain")
        if unresolved:
            self.stdout.write(
                self.style.WARNING(
                    "The following pull-through distributions require manual repair:"
                )
            )
            for distribution in unresolved:
                self.stdout.write(self._format_distribution(distribution))

        overlaps = find_container_distribution_overlaps()
        if overlaps:
            self.stdout.write(
                self.style.WARNING(
                    "The following container distributions have overlapping base paths:"
                )
            )
            for distribution, other in overlaps:
                self.stdout.write(
                    f"  {self._format_distribution(distribution).strip()} overlaps "
                    f"{self._format_distribution(other).strip()}"
                )

        if settings.CACHE_ENABLED and old_base_paths:
            SyncContentCache().delete(base_key=old_base_paths)
            self.stdout.write(self.style.SUCCESS("Flushed repaired distribution cache entries."))

    @staticmethod
    def _format_distribution(distribution):
        return (
            f"  domain={distribution.pulp_domain.name!r} pk={distribution.pk} "
            f"name={distribution.name!r} base_path={distribution.base_path!r}"
        )
