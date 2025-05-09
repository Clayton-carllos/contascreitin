document.addEventListener("DOMContentLoaded", function () {
    const dados = document.getElementById("dados");
    const receitas = JSON.parse(dados.dataset.receitas);
    const despesas = JSON.parse(dados.dataset.despesas);

    const labels = receitas.map(item => item.mes);

    const dadosReceitas = receitas.map(item => item.valor);
    const dadosDespesas = despesas.map(item => item.valor);

    const ctx = document.getElementById("graficoFinanceiro").getContext("2d");

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Receitas',
                    data: dadosReceitas,
                    borderColor: 'blue',
                    backgroundColor: 'rgba(0, 0, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Despesas',
                    data: dadosDespesas,
                    borderColor: 'red',
                    backgroundColor: 'rgba(255, 0, 0, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Receitas e Despesas por Mês'
                }
            }
        }
    });
});