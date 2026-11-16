from django.contrib import admin

from .models import Banner, DamageType, Item, Path, Pet, PetPool, PetPull, PetType, PetVariant, Warp

# Register your models here.

admin.site.register(Item)
admin.site.register(Warp)
admin.site.register(Banner)
admin.site.register(Path)
admin.site.register(DamageType)
admin.site.register(Pet)
admin.site.register(PetVariant)
admin.site.register(PetPool)
admin.site.register(PetType)
admin.site.register(PetPull)
