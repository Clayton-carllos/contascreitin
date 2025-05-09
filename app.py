from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
import csv
from io import StringIO
from flask import Response
from flask_migrate import Migrate
from sqlalchemy import cast, Numeric, Time
from flask_mail import Mail, Message
from flask import flash
import pytz
from flask import jsonify
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = 'your_secret_key' #Para conseguir usar o flash

#Configuração Banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://contas_db_user:iMnybI2hZl0JENjwfNDnKvZukKJz0D3Q@dpg-d0f584be5dus738dkorg-a.ohio-postgres.render.com/contas_db' #Id Banco de dados
app.config['SQLALCHEMY_TRACK_NOTIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Modelo banco de dados para LOGIN
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(200), nullable=False)

# Modelo banco de dados para Transacao
class Transition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    value = db.Column(Numeric(10, 2), nullable=False)
    typee = db.Column(db.String(120), nullable=False)
    date_transition = db.Column(db.Date, nullable=False)

# Modelo banco de dados para Transacao fixa
class FixedTransition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    value = db.Column(Numeric(10, 2), nullable=False)
    typee = db.Column(db.String(120), nullable=False)
    date_transition = db.Column(db.Date, nullable=False)

# Criar banco de dados e verificar se o admin existe
with app.app_context():
    db.create_all() # Certifica se as tabelas existem no banco de dados

    # Verifica o admin
    admin = Usuario.query.filter_by(username='admin').first()
    if not admin:
        senha_hash = generate_password_hash('admin123')
        usuario_admin = Usuario(username='admin', senha=senha_hash)
        db.session.add(usuario_admin)
        db.session.commit()
        print("Usuario admin criado com sucesso!")
    else:
        print("Usuario admin já  existe")

# Rota para exibir o formulário de agendamento
@app.route('/')
def index():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    nome_usuario = session.get('username')

    br_tz = pytz.timezone("America/Sao_Paulo")
    agora = datetime.now(br_tz)

    # Total geral
    receitas_total = Transition.query.filter_by(typee='Receita') \
        .with_entities(func.sum(cast(Transition.value, db.Float))).scalar() or 0

    despesas_total = FixedTransition.query.filter_by(typee='Despesa') \
        .with_entities(func.sum(cast(FixedTransition.value, db.Float))).scalar() or 0
    
    # Soma das receitas do mês atual
    receitas_mes = Transition.query.filter(
        extract('month', Transition.date_transition) == agora.month,
        extract('year', Transition.date_transition) == agora.year
    ).with_entities(func.sum(cast(Transition.value, db.Float))).scalar() or 0

    # Soma das despesas do mês atual
    despesas_mes = FixedTransition.query.filter(
        extract('month', FixedTransition.date_transition) == agora.month,
        extract('year', FixedTransition.date_transition) == agora.year
    ).with_entities(func.sum(cast(FixedTransition.value, db.Float))).scalar() or 0

    # Agrupar por mês (últimos 6 meses por exemplo)
    receitas_mensais = Transition.query.filter_by(typee='Receita') \
        .with_entities(
            extract('month', Transition.date_transition).label('mes'),
            func.sum(cast(Transition.value, db.Float)).label('valor')
        ).group_by('mes').order_by('mes').all()

    despesas_mensais = FixedTransition.query.filter_by(typee='Despesa') \
        .with_entities(
            extract('month', FixedTransition.date_transition).label('mes'),
            func.sum(cast(FixedTransition.value, db.Float)).label('valor')
        ).group_by('mes').order_by('mes').all()

    # Converte para estrutura usável no front
    def formatar_dados(mes_valor_list):
        nomes_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        return [{"mes": nomes_meses[int(mes)-1], "valor": float(valor)} for mes, valor in mes_valor_list]

    receitas_json = json.dumps(formatar_dados(receitas_mensais))
    despesas_json = json.dumps(formatar_dados(despesas_mensais))

    # Calcula saldo
    saldo_total = receitas_mes - despesas_mes

    return render_template(
        'home.html',
        receitas=receitas_total,
        despesas=despesas_total,
        saldo_total=saldo_total,
        nome_usuario=nome_usuario,
        receitas_json=receitas_json,
        despesas_json=despesas_json
    )

# Rota para processar a transação
@app.route('/transacao', methods=['GET', 'POST'])
def transacao():
    if request.method == 'POST':
        description = request.form['descricao']
        value = request.form['valor']
        typee = request.form['type']
        date_transition = datetime.strptime(request.form['data'], '%Y-%m-%d').date()

        # Caso contrário, cria o nova transacao
        novo_transacao = Transition(
            description=description, value=value, typee=typee, date_transition=date_transition
        )

        # Salvar no banco de dados
        db.session.add(novo_transacao)
        db.session.commit()

        # Flash de sucesso
        flash('Transação cadastrada com sucesso!', 'success')

        # Redireciona para a lista de transações ou para outra página
        return redirect(url_for('lista_transacoestotal'))

    # Caso seja uma requisição GET, obtém o parâmetro 'type' da URL
    typee = request.args.get('type')  # Acessa 'type' que vem da URL

    # Retorna o template que exibe o formulário ou faz algo com o 'typee'
    return render_template('transacao.html', typee=typee)

# Rota para processar a transação FIXA
@app.route('/transacaofixa', methods=['GET', 'POST'])
def transacaofixa():
    if request.method == 'POST':
        description = request.form['descricao']
        value = request.form['valor']
        typee = request.form['type']
        date_transition = datetime.strptime(request.form['data'], '%Y-%m-%d').date()

        # Caso contrário, cria o nova transacao FIXA
        novo_transacaofixa = FixedTransition(
            description=description, value=value, typee=typee, date_transition=date_transition
        )

        # Salvar no banco de dados
        db.session.add(novo_transacaofixa)
        db.session.commit()

        # Flash de sucesso
        flash('Transação cadastrada com sucesso!', 'success')

        # Redireciona para a lista de transações ou para outra página
        return redirect(url_for('lista_transacoestotal'))

    # Caso seja uma requisição GET, obtém o parâmetro 'type' da URL
    typee = request.args.get('type')  # Acessa 'type' que vem da URL

    # Retorna o template que exibe o formulário ou faz algo com o 'typee'
    return render_template('transacao.html', typee=typee)

# Rota para exibir um novo gastos
@app.route('/novo_gasto', methods=['GET', 'POST'])
def novo_gasto():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para adicionar um usuário.', 'warning')
        return redirect(url_for('login'))

    # Recupera o nome do usuário logado
    nome_usuario = session.get('username')  # Obtém o nome do usuário da sessão

    # Pega o parâmetro 'type' da URL
    tipo = request.args.get('type', default=None)

    gastos = Transition.query.all()

    return render_template('novo_gasto.html', nome_usuario=nome_usuario, gastos=gastos, tipo=tipo)

# Rota para exibir um novo gastos mensais
@app.route('/novo_gastomensal', methods=['GET', 'POST'])
def novo_gastomensal():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para adicionar um usuário.', 'warning')
        return redirect(url_for('login'))

    # Recupera o nome do usuário logado
    nome_usuario = session.get('username')  # Obtém o nome do usuário da sessão

    # Pega o parâmetro 'type' da URL
    tipo = request.args.get('type', default=None)

    gastos = FixedTransition.query.all()

    return render_template('novo_gastomensal.html', nome_usuario=nome_usuario, gastos=gastos, tipo=tipo)

#--------------------------------------------------------------------------------------------------------------------------------------------
# Rota para exibir o formulário de adicionar usuário
@app.route('/adicionar_usuario', methods=['GET', 'POST'])
def adicionar_usuario():
    
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para adicionar um usuário.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']

        # Verificar se o username já existe
        if Usuario.query.filter_by(username=username).first():
            flash('O nome de usuário já está em uso. Escolha outro.', 'danger')
            return render_template('adicionar_usuario.html')

        # Criação do hash da senha
        senha_hash = generate_password_hash(senha)

        # Criar o novo usuário
        novo_usuario = Usuario(username=username, senha=senha_hash)

        try:
            # Adicionar ao banco de dados
            db.session.add(novo_usuario)
            db.session.commit()

            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('lista_usuarios'))  # Redireciona para a lista de usuários
        except IntegrityError:
            db.session.rollback()  # Desfaz a transação se ocorrer um erro
            flash('Erro ao criar o usuário. Tente novamente.', 'danger')

    return render_template('adicionar_usuario.html')  # Exibe o formulário para adicionar usuário

# Rota para editar um usuário
@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)  # Busca o usuário pelo ID
    if request.method == 'POST':
        # Atualiza os campos do usuário
        usuario.username = request.form['username']
        usuario.senha = generate_password_hash(request.form['senha'])  # Atualiza a senha com hash

        # Salva no banco de dados
        db.session.commit()

        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('lista_usuarios'))  # Redireciona para a lista de usuários

    return render_template('editar_usuario.html', usuario=usuario)  # Exibe o formulário de edição

# Rota para listar usuários
@app.route('/usuarios')
def lista_usuarios():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Recupera o nome do usuário logado
    nome_usuario = session.get('username')  # Obtém o nome do usuário da sessão

    usuarios = Usuario.query.all()  # Recupera todos os usuários do banco de dados
    return render_template('lista_usuarios.html', usuarios=usuarios, nome_usuario=nome_usuario)

# Rota para exibir o perfil de um usuário
@app.route('/usuario/<int:id>')
def perfil_usuario(id):
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))

    usuario = Usuario.query.get_or_404(id)  # Recupera o usuário pelo ID
    return render_template('perfil_usuario.html', usuario=usuario)

# Rota para deletar um usuário
@app.route('/deletar_usuario/<int:id>', methods=['GET'])
def deletar_usuario(id):
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para realizar esta ação.', 'warning')
        return redirect(url_for('login'))

    usuario = Usuario.query.get_or_404(id)  # Recupera o usuário pelo ID
    db.session.delete(usuario)  # Exclui o usuário
    db.session.commit()  # Salva a mudança no banco de dados
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('lista_usuarios'))  # Redireciona para a lista de usuários

# Rota para exibir a página de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['username'] = usuario.username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    
    return render_template('login.html')

# Rota para exibir a lista de agendamentos
@app.route('/receitas')
def lista_transacoestotal():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Recupera o nome do usuário logado
    nome_usuario = session.get('username')  # Obtém o nome do usuário da sessão

    tabelas = Transition.query.all()


    return render_template('controlFinance.html', tabelas=tabelas, nome_usuario=nome_usuario)

#Rota para controles Fixos
@app.route('/depesas')
def lista_transacoesfixas():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Recupera o nome do usuário logado
    nome_usuariofixo = session.get('username')  # Obtém o nome do usuário da sessão

    fixas = FixedTransition.query.all()

    return render_template('controlFixo.html', fixas=fixas, nome_usuariofixo=nome_usuariofixo)


# Rota para exibir a Home

# Rota para exibir a Home
from sqlalchemy import extract, func, cast
import json

@app.route('/home')
def home():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    nome_usuario = session.get('username')

    br_tz = pytz.timezone("America/Sao_Paulo")
    agora = datetime.now(br_tz)

    # Total geral
    receitas_total = Transition.query.filter_by(typee='Receita') \
        .with_entities(func.sum(cast(Transition.value, db.Float))).scalar() or 0

    despesas_total = FixedTransition.query.filter_by(typee='Despesa') \
        .with_entities(func.sum(cast(FixedTransition.value, db.Float))).scalar() or 0
    
    # Soma das receitas do mês atual
    receitas_mes = Transition.query.filter(
        extract('month', Transition.date_transition) == agora.month,
        extract('year', Transition.date_transition) == agora.year
    ).with_entities(func.sum(cast(Transition.value, db.Float))).scalar() or 0

    # Soma das despesas do mês atual
    despesas_mes = FixedTransition.query.filter(
        extract('month', FixedTransition.date_transition) == agora.month,
        extract('year', FixedTransition.date_transition) == agora.year
    ).with_entities(func.sum(cast(FixedTransition.value, db.Float))).scalar() or 0

    # Agrupar por mês (últimos 6 meses por exemplo)
    receitas_mensais = Transition.query.filter_by(typee='Receita') \
        .with_entities(
            extract('month', Transition.date_transition).label('mes'),
            func.sum(cast(Transition.value, db.Float)).label('valor')
        ).group_by('mes').order_by('mes').all()

    despesas_mensais = FixedTransition.query.filter_by(typee='Despesa') \
        .with_entities(
            extract('month', FixedTransition.date_transition).label('mes'),
            func.sum(cast(FixedTransition.value, db.Float)).label('valor')
        ).group_by('mes').order_by('mes').all()

    # Converte para estrutura usável no front
    def formatar_dados(mes_valor_list):
        nomes_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        return [{"mes": nomes_meses[int(mes)-1], "valor": float(valor)} for mes, valor in mes_valor_list]

    receitas_json = json.dumps(formatar_dados(receitas_mensais))
    despesas_json = json.dumps(formatar_dados(despesas_mensais))

    # Calcula saldo
    saldo_total = receitas_mes - despesas_mes

    return render_template(
        'home.html',
        receitas=receitas_total,
        despesas=despesas_total,
        saldo_total=saldo_total,
        nome_usuario=nome_usuario,
        receitas_json=receitas_json,
        despesas_json=despesas_json
    )


# Rota para deletar um transação fixa
@app.route('/deletar/<tipo>/<int:id>')
def deletar(tipo, id):
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para realizar esta ação.', 'warning')
        return redirect(url_for('login'))

    if tipo == 'tabela':
        transacao = Transition.query.get_or_404(id)
        db.session.delete(transacao)
        db.session.commit()
        flash('Transação excluída com sucesso!', 'success')
        return redirect(url_for('lista_transacoestotal'))
    elif tipo == 'fixo':
        transacaofixa = FixedTransition.query.get_or_404(id)
        db.session.delete(transacaofixa)
        db.session.commit()
        flash('Transação excluída com sucesso!', 'success')
        return redirect(url_for('lista_transacoesfixas'))
    else:
        flash('Tipo inválido.', 'danger')
        return redirect(url_for('home'))
    

# Rota para editar uma transação
@app.route('/editar_transacao/<int:id>/<tipo>', methods=['GET', 'POST'])
def editar_transacao(id, tipo):
    if tipo == 'tabela':
        transacao = Transition.query.get_or_404(id)
        if request.method == 'POST':
            transacao.description = request.form['description']
            transacao.value = request.form['value']
            data_str = request.form['date_transition']
            transacao.date_transition = datetime.strptime(data_str, '%Y-%m-%d').date()
            db.session.commit()
            flash('Transação atualizada com sucesso!', 'success')
            return redirect(url_for('lista_transacoestotal'))
        return render_template('editar_transacao.html', transacao=transacao, tipo='tabela')

    elif tipo == 'fixo':
        transacao = FixedTransition.query.get_or_404(id)
        if request.method == 'POST':
            transacao.description = request.form['description']
            transacao.value = request.form['value']
            data_str = request.form['date_transition']
            transacao.date_transition = datetime.strptime(data_str, '%Y-%m-%d').date()
            db.session.commit()
            flash('Transação fixa atualizada com sucesso!', 'success')
            return redirect(url_for('lista_transacoesfixas'))
        return render_template('editar_transacao.html', transacao=transacao, tipo='fixo')

    # Se tipo não for reconhecido
    flash('Tipo inválido.', 'danger')
    return redirect(url_for('home'))  # <- garante que sempre há um retorno


#Rota para exportar relatorio
@app.route('/exportar-relatorio')
def exportar_relatorio():
    # Pega todos os agendamentos
    transacao = Transition.query.all() + FixedTransition.query.all()

    # Cria um buffer de StringIO para armazenar o CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Escreve o cabeçalho do CSV
    writer.writerow(['Descricao', 'Valor', 'Tipo', 'Data'])

    # Adiciona os dados dos agendamentos ao CSV
    for transacao in transacao:
        writer.writerow([transacao.description, transacao.value, transacao.typee])
    
    # Prepara o CSV para ser enviado como resposta
    output.seek(0)  # Volta o ponteiro do buffer para o início
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=relatorio_transacoes.csv"}
    )

# Rota para logout
@app.route('/logout', methods=['GET'])
def logout():
    session.pop('usuario_id', None)  # Remove a sessão do usuário
    session.pop('username', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))  # Redireciona para a página de login

if __name__ == "__main__":
    app.run(debug=True)


