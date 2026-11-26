class ReviewRouter:
    """Store reviews from both public forms and the CRM in the shared reviews database."""

    def db_for_read(self, model, **hints):
        return 'reviews' if model._meta.app_label == 'reviews' else None

    db_for_write = db_for_read

    def allow_migrate(self, db, app_label, **hints):
        if db == 'reviews' or app_label == 'reviews':
            return db == app_label == 'reviews'
        return None
