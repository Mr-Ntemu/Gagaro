from django.core.management.base import BaseCommand
from apps.recommendations.tasks import rebuild_all_profiles, cleanup_old_events


class Command(BaseCommand):
    help = 'Reconstruit les profils de recommandation de tous les clients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Nettoyer les anciens événements avant le rebuild'
        )
        parser.add_argument(
            '--days',
            type=int, default=180,
            help='Nombre de jours à conserver (défaut: 180)'
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            deleted = cleanup_old_events(options['days'])
            self.stdout.write(
                self.style.SUCCESS(f'{deleted} événements anciens supprimés.')
            )

        stats = rebuild_all_profiles()
        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuild terminé — "
                f"Succès: {stats['success']} | "
                f"Échecs: {stats['failed']} | "
                f"Skippés: {stats['skipped']}"
            )
        )
