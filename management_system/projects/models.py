from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

class Project(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    manager = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, related_name='managed_projects')
    team_members = models.ManyToManyField('employees.Employee', related_name='projects', blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    start_date = models.DateField()
    end_date = models.DateField()
    completion_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['company', 'name']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"

class SousTache(models.Model):
    STATUS_CHOICES = [
        ('a_faire', 'À faire'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('en_attente', 'En attente'),
        ('annule', 'Annulé'),
    ]
    
    PRIORITE_CHOICES = [
        ('faible', 'Faible'),
        ('moyenne', 'Moyenne'),
        ('elevee', 'Élevée'),
        ('urgente', 'Urgente'),
    ]
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='sous_taches')
    projet = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='sous_taches')
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigne_a = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='taches_assignees')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='a_faire')
    priorite = models.CharField(max_length=20, choices=PRIORITE_CHOICES, default='moyenne')
    date_debut = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    date_achevement = models.DateField(null=True, blank=True)
    duree_estimee = models.IntegerField(help_text="Durée estimée en heures", default=0)
    ordre = models.IntegerField(default=0)
    depend_de = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='dependances')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['ordre', 'created_at']
        verbose_name = 'Sous-tâche'
        verbose_name_plural = 'Sous-tâches'
    
    def __str__(self):
        return f"{self.titre} - {self.get_status_display()}"

class CommentaireTache(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='commentaires')
    tache = models.ForeignKey(SousTache, on_delete=models.CASCADE, related_name='commentaires')
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenu = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Commentaire par {self.auteur} sur {self.tache.titre}"