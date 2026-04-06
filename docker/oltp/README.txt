docker cp popular.sql relacional:/popular.sql
docker exec -i relacional psql -U relacional -d relacional -f /popular.sql

isto é pra popular pq o ficheiro é muito grande, se não inserir nada


PRA ACEDER AO PGADMIN JÁ ESTA INSTALADO: só ENTRAR e ver credenciais no docker-compose: http://localhost:8080/browser/

host: postgres_source
