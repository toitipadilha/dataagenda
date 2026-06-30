# 🦷 DentaAgenda

Sistema de agendamento odontológico — multi-tenant, Flask + PostgreSQL.

---

## Funcionalidades

- ✅ Login seguro (bcrypt)
- ✅ Agenda visual semanal (seg–sáb, 07h–18h)
- ✅ Cadastro de pacientes
- ✅ Consultas: criar, editar, excluir, mudar status
- ✅ WhatsApp via wa.me (lembrete automático com nome, data, hora)
- ✅ Tela TV sala de espera (sem login, atualiza a cada 30s)
- ✅ Multi-tenant (cada clínica é isolada por clinica_id)

---

## Deploy no Lightsail

### 1. Enviar arquivos

```bash
scp -r ./dentaagenda ubuntu@SEU_IP:~/
ssh ubuntu@SEU_IP
cd ~/dentaagenda
```

### 2. Rodar o deploy

```bash
chmod +x deploy.sh
bash deploy.sh
```

### 3. Editar senha do banco

```bash
nano /home/ubuntu/dentaagenda/.env
# Troque TROQUE_AQUI pela senha que quiser
# Depois reinicie:
sudo systemctl restart dentaagenda
```

### 4. Inicializar banco

```bash
cd /home/ubuntu/dentaagenda
source venv/bin/activate
python3 -c "from app import app, db; app.app_context().push(); db.create_all(); print('OK')"
```

### 5. Criar primeira clínica

Acesse: `http://SEU_IP/setup`

Preencha:
- Nome da clínica (ex: `Dra. Ana Lima Odontologia`)
- Slug (ex: `dra-ana-lima`) → URL da TV será `/tv/dra-ana-lima`
- E-mail e senha de acesso

---

## URLs importantes

| URL | O que é |
|-----|---------|
| `/login` | Login da dentista |
| `/agenda` | Agenda semanal |
| `/consultas` | Lista de consultas |
| `/pacientes` | Cadastro de pacientes |
| `/tv/dra-ana-lima` | Tela TV (sem login) |
| `/setup` | Configuração inicial (só funciona uma vez) |

---

## Porta

Roda na porta **5003** por padrão.

Se precisar mudar, edite `deploy.sh` e `app.py` (linha final).

---

## Adicionar nova clínica (multi-tenant)

Via terminal Python:

```python
from app import app, db
from app.models import Clinica, Usuario

with app.app_context():
    c = Clinica(nome='Clínica B', slug='clinica-b')
    db.session.add(c)
    db.session.flush()
    u = Usuario(clinica_id=c.id, nome='Dra. B', email='b@email.com', perfil='dentista')
    u.set_senha('senha123')
    db.session.add(u)
    db.session.commit()
```

---

## Status de consultas

| Status | Cor | Descrição |
|--------|-----|-----------|
| `pendente` | Amarelo | Agendado, sem confirmação |
| `confirmado` | Verde | Paciente confirmou |
| `em_atendimento` | Azul | Na cadeira agora |
| `finalizado` | Cinza | Consulta concluída |
| `cancelado` | Cinza claro | Cancelado |
