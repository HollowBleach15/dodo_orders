(function () {
    const products = JSON.parse(document.getElementById("products-data").textContent);
    const initialItems = JSON.parse(document.getElementById("items-data").textContent);

    const select = document.getElementById("product-select");
    const tbody = document.querySelector("#items-table tbody");
    const itemsJsonInput = document.getElementById("items_json");
    const discountInput = document.querySelector("[name='discount_percent']");

    products.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.name} — ${p.price.toFixed(2)} ₽`;
        opt.dataset.price = p.price;
        opt.dataset.name = p.name;
        select.appendChild(opt);
    });

    let items = initialItems.slice();

    function render() {
        tbody.innerHTML = "";
        let subtotal = 0;
        items.forEach((it, idx) => {
            const sum = it.price * it.quantity;
            subtotal += sum;
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${it.name}</td>
                <td><input type="number" min="1" value="${it.quantity}"
                      class="form-control form-control-sm qty" data-idx="${idx}" style="width:80px"></td>
                <td>${it.price.toFixed(2)} ₽</td>
                <td>${sum.toFixed(2)} ₽</td>
                <td><button type="button" class="btn btn-sm btn-outline-danger remove" data-idx="${idx}">✕</button></td>`;
            tbody.appendChild(tr);
        });

        const discount = parseFloat(discountInput.value || 0);
        const discSum = subtotal * discount / 100;
        const total = subtotal - discSum;

        document.getElementById("subtotal").textContent = subtotal.toFixed(2) + " ₽";
        document.getElementById("discount-sum").textContent = discSum.toFixed(2) + " ₽";
        document.getElementById("total").textContent = total.toFixed(2) + " ₽";

        itemsJsonInput.value = JSON.stringify(
            items.map(i => ({
                product_id: i.product_id,
                quantity: i.quantity
            }))
        );
    }

    document.getElementById("add-item").addEventListener("click", () => {
        const opt = select.options[select.selectedIndex];
        if (!opt.value) {
            alert("Выберите товар");
            return;
        }
        const qty = parseInt(document.getElementById("qty-input").value) || 1;
        const existing = items.find(i => i.product_id == opt.value);
        if (existing) existing.quantity += qty;
        else {
            items.push({
                product_id: parseInt(opt.value),
                name: opt.dataset.name,
                price: parseFloat(opt.dataset.price),
                quantity: qty
            });
        }
        render();
    });

    tbody.addEventListener("click", e => {
        if (e.target.classList.contains("remove")) {
            items.splice(parseInt(e.target.dataset.idx), 1);
            render();
        }
    });

    tbody.addEventListener("input", e => {
        if (e.target.classList.contains("qty")) {
            const v = parseInt(e.target.value) || 1;
            items[parseInt(e.target.dataset.idx)].quantity = Math.max(1, v);
            render();
        }
    });

    discountInput.addEventListener("input", render);

    document.getElementById("order-form").addEventListener("submit", e => {
        if (items.length === 0) {
            e.preventDefault();
            alert("Добавьте хотя бы одну позицию в заказ");
        }
    });

    render();
})();