# verify tables in postgres
```
docker exec -it beam_ai_db psql -U beam_ai -d beam_ai -c "\dt"
```