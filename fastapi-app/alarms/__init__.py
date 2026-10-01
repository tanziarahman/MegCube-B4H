"""Alarms: box records -> events -> rules -> incidents -> emails.

  normalize  one box record -> one events row (pure)
  rules      does an event match a rule? time windows, who, thresholds (pure)
  engine     fires the rules for new events: cooldown, grouping, incidents, queued emails
  ingest     polls the box's alarm_history and saves events; syncs cameras
  mailer     SMTP settings, email content, the email queue worker
  worker     background loops started with the app
"""
