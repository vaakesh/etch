инструкция по запуску:
1. настроить секреты .env (поменяйте значения)
```zsh
cp .env.example .env
cp backend/.env.example backend/.env
```
2. сегенерировать jwt-ключи
```zsh
openssl genpkey -algorithm RSA -out backend/certs/jwt-private.pem -pkeyopt rsa_keygen_bits:2048
openssl pkey -in backend/certs/jwt-private.pem -pubout -out backend/certs/jwt-public.pem
```
3. поднять инфраструктуру
```zsh
make up
```
4. готово -> http://localhost:5173