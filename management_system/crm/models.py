from django.db import models

# Create your models here.


class Contact(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['company', 'email']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Opportunity(models.Model):
    STAGE_CHOICES = [
        ('prospect', 'Prospect'),
        ('qualified', 'Qualified'),
        ('proposal', 'Proposal'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='opportunities')
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='opportunities')
    title = models.CharField(max_length=200)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='prospect')
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.contact.name})"

    # helper properties/methods
    @property
    def is_won(self):
        return self.stage == 'won'

    @property
    def is_lost(self):
        return self.stage == 'lost'

    def advance_stage(self, new_stage):
        """Advance opportunity to a new stage following allowed transitions."""
        allowed = [choice[0] for choice in self.STAGE_CHOICES]
        if new_stage not in allowed:
            raise ValueError(f"Invalid stage '{new_stage}'")
        self.stage = new_stage
        self.save()