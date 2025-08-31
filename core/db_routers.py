class ReadReplicaRouter:
    """Route SAFE reads to replica if configured; writes go to default."""
    def db_for_read(self, model, **hints):
        from django.conf import settings
        if getattr(settings, 'DATABASES', {}).get('replica'):
            return 'replica'
        return None
    def db_for_write(self, model, **hints):
        return 'default'
    def allow_relation(self, obj1, obj2, **hints):
        return True
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True
