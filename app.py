import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///dentaagenda.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db      = SQLAlchemy(app)
bcrypt  = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para continuar.'

# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class Clinica(db.Model):
    __tablename__ = 'clinicas'
    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(120), nullable=False)
    slug      = db.Column(db.String(60), unique=True, nullable=False)  # ex: dra-ana-lima
    telefone  = db.Column(db.String(20))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuarios  = db.relationship('Usuario', backref='clinica', lazy=True)
    pacientes = db.relationship('Paciente', backref='clinica', lazy=True)
    consultas = db.relationship('Consulta', backref='clinica', lazy=True)
    horarios  = db.relationship('HorarioBloqueado', backref='clinica', lazy=True)


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id         = db.Column(db.Integer, primary_key=True)
    clinica_id = db.Column(db.Integer, db.ForeignKey('clinicas.id'), nullable=False)
    nome       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil     = db.Column(db.String(20), default='dentista')  # dentista | recepcao

    def set_senha(self, senha):
        self.senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')

    def check_senha(self, senha):
        return bcrypt.check_password_hash(self.senha_hash, senha)


class Paciente(db.Model):
    __tablename__ = 'pacientes'
    id         = db.Column(db.Integer, primary_key=True)
    clinica_id = db.Column(db.Integer, db.ForeignKey('clinicas.id'), nullable=False)
    nome       = db.Column(db.String(120), nullable=False)
    telefone   = db.Column(db.String(20))
    nascimento = db.Column(db.Date)
    obs        = db.Column(db.Text)
    criado_em  = db.Column(db.DateTime, default=datetime.utcnow)
    consultas  = db.relationship('Consulta', backref='paciente', lazy=True)


class Consulta(db.Model):
    __tablename__ = 'consultas'
    id           = db.Column(db.Integer, primary_key=True)
    clinica_id   = db.Column(db.Integer, db.ForeignKey('clinicas.id'), nullable=False)
    paciente_id  = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    data         = db.Column(db.Date, nullable=False)
    hora         = db.Column(db.String(5), nullable=False)   # "09:00"
    procedimento = db.Column(db.String(120))
    status       = db.Column(db.String(20), default='pendente')  # pendente | confirmado | em_atendimento | finalizado | cancelado
    obs          = db.Column(db.Text)
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)


class HorarioBloqueado(db.Model):
    __tablename__ = 'horarios_bloqueados'
    id         = db.Column(db.Integer, primary_key=True)
    clinica_id = db.Column(db.Integer, db.ForeignKey('clinicas.id'), nullable=False)
    data       = db.Column(db.Date, nullable=False)
    hora       = db.Column(db.String(5), nullable=False)
    motivo     = db.Column(db.String(100))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

HORARIOS = [
    '07:00','07:30','08:00','08:30','09:00','09:30',
    '10:00','10:30','11:00','11:30',
    '13:00','13:30','14:00','14:30','15:00','15:30',
    '16:00','16:30','17:00','17:30','18:00'
]

DIAS_SEMANA = ['Seg','Ter','Qua','Qui','Sex','Sáb']

def get_semana(offset=0):
    """Retorna lista de dates (seg a sáb) da semana com offset."""
    hoje = date.today()
    dow  = hoje.weekday()  # 0=seg
    inicio = hoje - timedelta(days=dow) + timedelta(weeks=offset)
    return [inicio + timedelta(days=i) for i in range(6)]

def wa_link(telefone, mensagem):
    n = ''.join(filter(str.isdigit, telefone))
    if not n.startswith('55'):
        n = '55' + n
    from urllib.parse import quote
    return f'https://wa.me/{n}?text={quote(mensagem)}'

def build_wa_msg(paciente, consulta):
    d = consulta.data.strftime('%d/%m/%Y')
    primeiro_nome = paciente.nome.split()[0]
    proc = f'\nProcedimento: {consulta.procedimento}' if consulta.procedimento else ''
    return (
        f'Olá {primeiro_nome}! 😊\n'
        f'Lembrando sua consulta no dia *{d}* às *{consulta.hora}*.{proc}\n'
        f'Até lá! 🦷'
    )


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('agenda'))
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        senha = request.form.get('senha','')
        user  = Usuario.query.filter_by(email=email).first()
        if user and user.check_senha(senha):
            login_user(user, remember=True)
            return redirect(url_for('agenda'))
        flash('E-mail ou senha incorretos.', 'erro')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
# AGENDA
# ─────────────────────────────────────────────

@app.route('/')
@login_required
def agenda():
    return redirect(url_for('agenda_semana'))

@app.route('/agenda')
@login_required
def agenda_semana():
    offset = int(request.args.get('offset', 0))
    dias   = get_semana(offset)
    cid    = current_user.clinica_id

    consultas = Consulta.query.filter(
        Consulta.clinica_id == cid,
        Consulta.data >= dias[0],
        Consulta.data <= dias[-1]
    ).all()

    bloqueados = HorarioBloqueado.query.filter(
        HorarioBloqueado.clinica_id == cid,
        HorarioBloqueado.data >= dias[0],
        HorarioBloqueado.data <= dias[-1]
    ).all()

    # mapa: (data_str, hora) → consulta
    mapa = {}
    for c in consultas:
        mapa[(c.data.isoformat(), c.hora)] = c

    bloq_set = set()
    for b in bloqueados:
        bloq_set.add((b.data.isoformat(), b.hora))

    return render_template('agenda.html',
        dias=dias, horarios=HORARIOS, mapa=mapa, bloq_set=bloq_set,
        offset=offset, dias_label=DIAS_SEMANA, hoje=date.today()
    )


# ─────────────────────────────────────────────
# CONSULTAS
# ─────────────────────────────────────────────

@app.route('/consultas')
@login_required
def consultas():
    cid  = current_user.clinica_id
    data_filtro = request.args.get('data')
    q = Consulta.query.filter_by(clinica_id=cid)
    if data_filtro:
        try:
            q = q.filter(Consulta.data == date.fromisoformat(data_filtro))
        except ValueError:
            pass
    lista = q.order_by(Consulta.data, Consulta.hora).all()
    pacientes = Paciente.query.filter_by(clinica_id=cid).order_by(Paciente.nome).all()
    return render_template('consultas.html', consultas=lista, pacientes=pacientes,
                           data_filtro=data_filtro, wa_link=wa_link, build_wa_msg=build_wa_msg)

@app.route('/consultas/nova', methods=['POST'])
@login_required
def nova_consulta():
    cid = current_user.clinica_id
    pac_id = request.form.get('paciente_id')
    data_str = request.form.get('data')
    hora     = request.form.get('hora')
    if not (pac_id and data_str and hora):
        flash('Preencha paciente, data e horário.', 'erro')
        return redirect(request.referrer or url_for('agenda_semana'))
    c = Consulta(
        clinica_id   = cid,
        paciente_id  = int(pac_id),
        data         = date.fromisoformat(data_str),
        hora         = hora,
        procedimento = request.form.get('procedimento','').strip(),
        status       = request.form.get('status','pendente'),
        obs          = request.form.get('obs','').strip()
    )
    db.session.add(c)
    db.session.commit()
    flash('Consulta agendada!', 'ok')
    return redirect(request.referrer or url_for('agenda_semana'))

@app.route('/consultas/<int:cid_>/editar', methods=['POST'])
@login_required
def editar_consulta(cid_):
    c = Consulta.query.filter_by(id=cid_, clinica_id=current_user.clinica_id).first_or_404()
    c.paciente_id  = int(request.form.get('paciente_id', c.paciente_id))
    c.data         = date.fromisoformat(request.form.get('data', c.data.isoformat()))
    c.hora         = request.form.get('hora', c.hora)
    c.procedimento = request.form.get('procedimento','').strip()
    c.status       = request.form.get('status', c.status)
    c.obs          = request.form.get('obs','').strip()
    db.session.commit()
    flash('Consulta atualizada!', 'ok')
    return redirect(request.referrer or url_for('agenda_semana'))

@app.route('/consultas/<int:cid_>/excluir', methods=['POST'])
@login_required
def excluir_consulta(cid_):
    c = Consulta.query.filter_by(id=cid_, clinica_id=current_user.clinica_id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    flash('Consulta excluída.', 'ok')
    return redirect(request.referrer or url_for('agenda_semana'))

@app.route('/consultas/<int:cid_>/status', methods=['POST'])
@login_required
def mudar_status(cid_):
    c = Consulta.query.filter_by(id=cid_, clinica_id=current_user.clinica_id).first_or_404()
    c.status = request.form.get('status', c.status)
    db.session.commit()
    return jsonify({'ok': True, 'status': c.status})

# API para modal de detalhe
@app.route('/api/consulta/<int:cid_>')
@login_required
def api_consulta(cid_):
    c = Consulta.query.filter_by(id=cid_, clinica_id=current_user.clinica_id).first_or_404()
    p = c.paciente
    wa = ''
    if p.telefone:
        wa = wa_link(p.telefone, build_wa_msg(p, c))
    return jsonify({
        'id': c.id,
        'paciente': p.nome,
        'paciente_id': p.id,
        'telefone': p.telefone or '',
        'data': c.data.isoformat(),
        'hora': c.hora,
        'procedimento': c.procedimento or '',
        'status': c.status,
        'obs': c.obs or '',
        'wa_link': wa
    })


# ─────────────────────────────────────────────
# PACIENTES
# ─────────────────────────────────────────────

@app.route('/pacientes')
@login_required
def pacientes():
    cid  = current_user.clinica_id
    q    = request.args.get('q','').strip()
    lista = Paciente.query.filter_by(clinica_id=cid)
    if q:
        lista = lista.filter(Paciente.nome.ilike(f'%{q}%'))
    lista = lista.order_by(Paciente.nome).all()
    return render_template('pacientes.html', pacientes=lista, q=q, wa_link=wa_link)

@app.route('/pacientes/novo', methods=['POST'])
@login_required
def novo_paciente():
    cid  = current_user.clinica_id
    nome = request.form.get('nome','').strip()
    if not nome:
        flash('Informe o nome do paciente.', 'erro')
        return redirect(url_for('pacientes'))
    nasc_str = request.form.get('nascimento','')
    nasc = date.fromisoformat(nasc_str) if nasc_str else None
    p = Paciente(
        clinica_id = cid,
        nome       = nome,
        telefone   = request.form.get('telefone','').strip(),
        nascimento = nasc,
        obs        = request.form.get('obs','').strip()
    )
    db.session.add(p)
    db.session.commit()
    flash('Paciente cadastrado!', 'ok')
    return redirect(url_for('pacientes'))

@app.route('/pacientes/<int:pid>/editar', methods=['POST'])
@login_required
def editar_paciente(pid):
    p = Paciente.query.filter_by(id=pid, clinica_id=current_user.clinica_id).first_or_404()
    p.nome     = request.form.get('nome', p.nome).strip()
    p.telefone = request.form.get('telefone','').strip()
    nasc_str   = request.form.get('nascimento','')
    p.nascimento = date.fromisoformat(nasc_str) if nasc_str else None
    p.obs      = request.form.get('obs','').strip()
    db.session.commit()
    flash('Paciente atualizado!', 'ok')
    return redirect(url_for('pacientes'))

@app.route('/pacientes/<int:pid>/excluir', methods=['POST'])
@login_required
def excluir_paciente(pid):
    p = Paciente.query.filter_by(id=pid, clinica_id=current_user.clinica_id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    flash('Paciente excluído.', 'ok')
    return redirect(url_for('pacientes'))

@app.route('/api/paciente/<int:pid>')
@login_required
def api_paciente(pid):
    p = Paciente.query.filter_by(id=pid, clinica_id=current_user.clinica_id).first_or_404()
    return jsonify({
        'id': p.id, 'nome': p.nome, 'telefone': p.telefone or '',
        'nascimento': p.nascimento.isoformat() if p.nascimento else '',
        'obs': p.obs or ''
    })


# ─────────────────────────────────────────────
# TELA TV
# ─────────────────────────────────────────────

@app.route('/tv/<slug>')
def tv(slug):
    clinica = Clinica.query.filter_by(slug=slug).first_or_404()
    hoje    = date.today()
    consultas = Consulta.query.filter_by(clinica_id=clinica.id, data=hoje)\
        .filter(Consulta.status != 'cancelado')\
        .order_by(Consulta.hora).all()
    return render_template('tv.html', clinica=clinica, consultas=consultas, hoje=hoje)

@app.route('/api/tv/<slug>')
def api_tv(slug):
    clinica = Clinica.query.filter_by(slug=slug).first_or_404()
    hoje    = date.today()
    consultas = Consulta.query.filter_by(clinica_id=clinica.id, data=hoje)\
        .filter(Consulta.status != 'cancelado')\
        .order_by(Consulta.hora).all()
    return jsonify([{
        'nome': c.paciente.nome.split()[0] + ' ' + c.paciente.nome.split()[-1] if len(c.paciente.nome.split()) > 1 else c.paciente.nome,
        'hora': c.hora,
        'status': c.status
    } for c in consultas])


# ─────────────────────────────────────────────
# SETUP INICIAL (criar clínica + usuário admin)
# ─────────────────────────────────────────────

@app.route('/setup', methods=['GET','POST'])
def setup():
    if Clinica.query.count() > 0:
        return redirect(url_for('login'))
    if request.method == 'POST':
        clinica = Clinica(
            nome     = request.form['nome_clinica'].strip(),
            slug     = request.form['slug'].strip().lower().replace(' ','-'),
            telefone = request.form.get('telefone','').strip()
        )
        db.session.add(clinica)
        db.session.flush()
        user = Usuario(
            clinica_id = clinica.id,
            nome       = request.form['nome_usuario'].strip(),
            email      = request.form['email'].strip().lower(),
            perfil     = 'dentista'
        )
        user.set_senha(request.form['senha'])
        db.session.add(user)
        db.session.commit()
        flash('Sistema configurado! Faça login.', 'ok')
        return redirect(url_for('login'))
    return render_template('setup.html')


# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, host='0.0.0.0', port=5003)
