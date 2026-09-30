from django.contrib import admin

from .models import Banner, DamageType, Item, Path, Warp

# Register your models here.

admin.site.register(Item)
admin.site.register(Warp)
admin.site.register(Banner)
admin.site.register(Path)
admin.site.register(DamageType)
