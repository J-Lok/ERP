class CompanyScopedFormMixin:
    """
    Mixin for ModelForms whose underlying model has unique_together or scope constraints with company.
    Injects company into instance prior to validation so unique_together checks work cleanly in forms.
    """

    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        if self.company and hasattr(self.instance, 'company') and not getattr(self.instance, 'company_id', None):
            self.instance.company = self.company

    def clean(self):
        if self.company and hasattr(self.instance, 'company') and not getattr(self.instance, 'company_id', None):
            self.instance.company = self.company
        return super().clean()
