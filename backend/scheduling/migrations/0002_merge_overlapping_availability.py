# Normalize availability: merge overlapping blocks for the same psychologist on
# the same weekday (or same one-off date). Overlaps made the booking capacity
# check double-count appointments. Merged window = union of the overlapping
# windows; merged capacity = sum, so the total number of bookable slots is kept.
# Adjacent (touching, non-overlapping) windows are left alone - they partition
# the day intentionally.

from collections import defaultdict

from django.db import migrations


def merge_overlaps(apps, schema_editor):
    AvailabilityBlock = apps.get_model("scheduling", "AvailabilityBlock")
    groups = defaultdict(list)
    for b in AvailabilityBlock.objects.filter(active=True).order_by("start_time", "id"):
        if b.date is None and b.weekday is None:
            continue  # dead block, unbookable either way
        key = ((b.psychologist_id, "date", b.date) if b.date is not None
               else (b.psychologist_id, "weekday", b.weekday))
        groups[key].append(b)
    for blocks in groups.values():
        current = None
        for b in blocks:
            if current is not None and b.start_time < current.end_time:
                current.end_time = max(current.end_time, b.end_time)
                current.capacity = (current.capacity or 0) + (b.capacity or 0)
                current.save()
                b.delete()
            else:
                current = b


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(merge_overlaps, migrations.RunPython.noop),
    ]
