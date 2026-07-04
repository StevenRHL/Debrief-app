"""Shared code packaged alongside each Debrief Lambda.

In AWS, this directory is copied into each function's deployment bundle so
`from shared.grading import ...` resolves. Locally, the handlers, the local API
server, and the stress-test harness all put `lambdas/` on sys.path.
"""
