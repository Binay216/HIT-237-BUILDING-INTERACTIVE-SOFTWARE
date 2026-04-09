from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from repairs.models import (
    Community, Dwelling, TenantProfile, RepairRequest,
    MaintenanceLog, Notification, RepairFeedback
)


class Command(BaseCommand):
    help = 'Seeds the database with sample NT remote housing data for development and demo.'

    COMMUNITIES = [
        ('Wadeye', 'TOP_END', 2500),
        ('Maningrida', 'TOP_END', 2900),
        ('Yuendumu', 'CENTRAL', 800),
        ('Hermannsburg', 'CENTRAL', 600),
        ('Borroloola', 'BIG_RIVERS', 900),
        ('Numbulwar', 'EAST_ARNHEM', 750),
        ('Ali Curung', 'BARKLY', 500),
    ]

    DWELLINGS = [
        ('12 Main Road', 'Wadeye', 'HOUSE', 3, 2005, False),
        ('5 Creek Street', 'Wadeye', 'HOUSE', 4, 2010, True),
        ('8 Bush Lane', 'Maningrida', 'DUPLEX', 2, 1998, False),
        ('1 Desert View', 'Yuendumu', 'HOUSE', 3, 2015, True),
        ('22 River Road', 'Hermannsburg', 'TOWN_CAMP', 2, 1990, False),
        ('3 Coastal Drive', 'Borroloola', 'HOUSE', 4, 2020, True),
        ('15 Arnhem Way', 'Numbulwar', 'UNIT', 2, 2000, False),
        ('7 Outback Street', 'Ali Curung', 'HOUSE', 3, 2012, True),
    ]

    TENANTS = [
        ('sarah', 'Sarah', 'Johnson', 0),
        ('david', 'David', 'Williams', 1),
        ('emily', 'Emily', 'Brown', 2),
    ]

    REPAIR_REQUESTS = [
        (0, 0, 'Air conditioner not working',
         'The AC unit in the bedroom has stopped producing cold air. Makes loud noise when turned on.',
         'AC', 'HIGH', 'BEDROOM'),
        (0, 0, 'Leaking kitchen tap',
         'Kitchen tap drips constantly. Water pooling under the sink.',
         'PLUMBING', 'MEDIUM', 'KITCHEN'),
        (1, 1, 'Front door lock broken',
         'Cannot lock the front door. Lock mechanism is jammed.',
         'DOOR_LOCK', 'EMERGENCY', 'OTHER'),
        (1, 1, 'Roof leak in bathroom',
         'Water comes through ceiling when it rains. Ceiling has brown stain.',
         'ROOF', 'HIGH', 'BATHROOM'),
        (2, 2, 'Power outlet sparking',
         'Living room power outlet sparks when plugging in appliances.',
         'ELECTRICAL', 'EMERGENCY', 'LIVING'),
        (2, 2, 'Termite damage under house',
         'Visible termite damage to floor joists. Floor feels soft in spots.',
         'PEST', 'HIGH', 'WHOLE'),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Clear all existing data before seeding.',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self._clear_data()

        communities = self._create_communities()
        dwellings = self._create_dwellings(communities)
        self._create_admin()
        staff = self._create_staff()
        tenants = self._create_tenants(dwellings)
        self._create_repair_requests(tenants, dwellings, staff)
        self._create_notifications(tenants, staff)

        self.stdout.write(self.style.SUCCESS('Seed data created successfully!'))

    def _clear_data(self):
        self.stdout.write('Clearing existing data...')
        RepairFeedback.objects.all().delete()
        Notification.objects.all().delete()
        MaintenanceLog.objects.all().delete()
        RepairRequest.objects.all().delete()
        TenantProfile.objects.all().delete()
        Dwelling.objects.all().delete()
        Community.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.WARNING('All data cleared.'))

    def _create_communities(self):
        communities = {}
        for name, region, pop in self.COMMUNITIES:
            community, created = Community.objects.get_or_create(
                name=name, defaults={'region': region, 'population': pop}
            )
            communities[name] = community
            if created:
                self.stdout.write(f'  Created community: {name}')
        self.stdout.write(self.style.SUCCESS(
            f'Communities: {Community.objects.count()}'
        ))
        return communities

    def _create_dwellings(self, communities):
        dwellings = []
        for addr, comm, dtype, beds, year, ncc in self.DWELLINGS:
            dwelling, created = Dwelling.objects.get_or_create(
                address=addr, community=communities[comm],
                defaults={
                    'dwelling_type': dtype, 'bedrooms': beds,
                    'year_built': year, 'meets_ncc_standards': ncc,
                }
            )
            dwellings.append(dwelling)
            if created:
                self.stdout.write(f'  Created dwelling: {addr}')
        self.stdout.write(self.style.SUCCESS(
            f'Dwellings: {Dwelling.objects.count()}'
        ))
        return dwellings

    def _create_admin(self):
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                'admin', '', 'admin123'
            )
            # Signal auto-creates profile; update it
            TenantProfile.objects.update_or_create(
                user=admin_user,
                defaults={'is_staff_member': True, 'phone': '0400000000'}
            )
            self.stdout.write(self.style.SUCCESS(
                'Superuser created: admin / admin123'
            ))

    def _create_staff(self):
        if not User.objects.filter(username='mike').exists():
            staff_user = User.objects.create_user(
                'mike', password='pass1234',
                first_name='Mike', last_name='Wilson'
            )
            # Signal auto-creates profile; update it
            TenantProfile.objects.update_or_create(
                user=staff_user,
                defaults={'is_staff_member': True, 'phone': '0400000099'}
            )
            self.stdout.write(self.style.SUCCESS(
                'Staff user created: mike / pass1234'
            ))
            return staff_user.profile
        return User.objects.get(username='mike').profile

    def _create_tenants(self, dwellings):
        tenants = []
        for username, first, last, dwelling_idx in self.TENANTS:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username, password='pass1234',
                    first_name=first, last_name=last
                )
                # Signal auto-creates profile; update it
                TenantProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        'dwelling': dwellings[dwelling_idx],
                        'phone': f'04000000{len(tenants)+1}',
                    }
                )
                tenants.append(user.profile)
                self.stdout.write(f'  Created tenant: {username}')
            else:
                tenants.append(
                    User.objects.get(username=username).profile
                )
        self.stdout.write(self.style.SUCCESS(
            f'Tenants: {len(tenants)}'
        ))
        return tenants

    def _create_repair_requests(self, tenants, dwellings, staff):
        for t_idx, d_idx, title, desc, itype, priority, loc in self.REPAIR_REQUESTS:
            request, created = RepairRequest.objects.get_or_create(
                title=title, tenant=tenants[t_idx],
                defaults={
                    'dwelling': dwellings[d_idx],
                    'description': desc,
                    'issue_type': itype,
                    'priority': priority,
                    'location_in_dwelling': loc,
                }
            )
            if created:
                self.stdout.write(f'  Created request: {title}')

        # Set some requests to different statuses for demo
        requests = list(RepairRequest.objects.order_by('created_at'))
        if len(requests) >= 2 and requests[0].status == 'PENDING':
            requests[0].mark_in_review()
            MaintenanceLog.objects.get_or_create(
                repair_request=requests[0], author=staff,
                defaults={
                    'note': 'Reviewing request. Will schedule inspection.',
                    'status_change': 'IN_REVIEW',
                }
            )
        if len(requests) >= 2 and requests[1].status == 'PENDING':
            requests[1].mark_in_progress(staff)
            MaintenanceLog.objects.get_or_create(
                repair_request=requests[1], author=staff,
                defaults={
                    'note': 'Plumber scheduled for next Tuesday.',
                    'status_change': 'IN_PROGRESS',
                }
            )
        if len(requests) >= 6 and requests[5].status == 'PENDING':
            requests[5].mark_completed()
            MaintenanceLog.objects.get_or_create(
                repair_request=requests[5], author=staff,
                defaults={
                    'note': 'Pest control treatment completed. Follow-up in 3 months.',
                    'status_change': 'COMPLETED',
                }
            )
            # Add feedback for the completed request
            RepairFeedback.objects.get_or_create(
                repair_request=requests[5],
                defaults={
                    'tenant': requests[5].tenant,
                    'rating': 4,
                    'comment': 'Good work, pest issue seems resolved. Will monitor.',
                }
            )

        self.stdout.write(self.style.SUCCESS(
            f'Repair requests: {RepairRequest.objects.count()}'
        ))

    def _create_notifications(self, tenants, staff):
        if Notification.objects.exists():
            return

        # Welcome notifications
        for tenant in tenants:
            Notification.objects.create(
                recipient=tenant,
                title='Welcome to NT Housing Repairs',
                message='You can now submit repair requests for your dwelling.',
                notification_type='SYSTEM',
            )

        # System notification for staff
        Notification.objects.create(
            recipient=staff,
            title='New staff account activated',
            message='You now have access to manage repair requests across all communities.',
            notification_type='SYSTEM',
        )

        self.stdout.write(self.style.SUCCESS(
            f'Notifications: {Notification.objects.count()}'
        ))
