<template>
  <div class="restocking">
    <div class="page-header">
      <h2>Restocking</h2>
      <p>Budget-based restock recommendations based on current inventory levels and forecasted demand.</p>
    </div>

    <div v-if="successMessage" class="success-banner">
      {{ successMessage }}
    </div>

    <div class="card budget-card">
      <div class="card-header">
        <h3 class="card-title">Budget</h3>
      </div>
      <div class="budget-body">
        <div class="slider-row">
          <span class="slider-label">Budget</span>
          <span class="slider-value">{{ formatCurrency(budget) }}</span>
        </div>
        <input
          type="range"
          v-model.number="budget"
          min="10000"
          max="500000"
          step="5000"
          class="budget-slider"
        />
        <div class="budget-chips" v-if="summary">
          <div class="stat-chip">
            <span class="chip-label">Budget</span>
            <span class="chip-value">{{ formatCurrency(summary.budget) }}</span>
          </div>
          <div class="stat-chip allocated">
            <span class="chip-label">Allocated</span>
            <span class="chip-value">{{ formatCurrency(summary.spent) }}</span>
          </div>
          <div class="stat-chip remaining">
            <span class="chip-label">Remaining</span>
            <span class="chip-value">{{ formatCurrency(summary.remaining) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="card">
      <div class="card-header">
        <h3 class="card-title">
          Recommendations
          <span v-if="!loading" class="count-badge">{{ recommendations.length }}</span>
        </h3>
      </div>

      <div v-if="loading" class="loading">Loading...</div>
      <div v-else>
        <div class="table-container">
          <table v-if="recommendations.length > 0">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Category</th>
                <th>On Hand</th>
                <th>Reorder Pt</th>
                <th>Forecast</th>
                <th>Qty</th>
                <th>Unit Cost</th>
                <th>Line Cost</th>
                <th>Urgency</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.sku">
                <td><strong>{{ rec.sku }}</strong></td>
                <td>{{ rec.name }}</td>
                <td>{{ rec.category }}</td>
                <td>{{ rec.quantity_on_hand }}</td>
                <td>{{ rec.reorder_point }}</td>
                <td>{{ rec.forecasted_demand }}</td>
                <td><strong>{{ rec.recommended_quantity }}</strong></td>
                <td>${{ rec.unit_cost.toFixed(2) }}</td>
                <td>{{ formatCurrency(rec.line_cost) }}</td>
                <td>
                  <div class="urgency-track">
                    <div
                      class="urgency-fill"
                      :class="getUrgencyClass(rec.urgency)"
                      :style="{ width: (rec.urgency * 100) + '%' }"
                    ></div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-state">No items below reorder point.</div>
        </div>

        <div v-if="recommendations.length > 0" class="table-footer">
          <span class="footer-total">
            Total: <strong>{{ formatCurrency(totalLineCost) }}</strong>
          </span>
          <button
            class="btn-primary"
            :disabled="submitting"
            @click="placeOrder"
          >
            {{ submitting ? 'Placing Order...' : 'Place Order' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'

export default {
  name: 'Restocking',
  setup() {
    const budget = ref(100000)
    const loading = ref(false)
    const error = ref(null)
    const submitting = ref(false)
    const successMessage = ref(null)
    const summary = ref(null)
    const recommendations = ref([])

    let debounceTimer = null

    const totalLineCost = computed(() => {
      return recommendations.value.reduce((sum, r) => sum + r.line_cost, 0)
    })

    const formatCurrency = (value) => {
      return value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
    }

    const getUrgencyClass = (urgency) => {
      if (urgency > 0.7) return 'urgency-high'
      if (urgency > 0.3) return 'urgency-medium'
      return 'urgency-low'
    }

    const loadRecommendations = async () => {
      loading.value = true
      error.value = null
      try {
        const data = await api.getRestockingRecommendations(budget.value)
        summary.value = {
          budget: data.budget,
          spent: data.spent,
          remaining: data.remaining
        }
        recommendations.value = data.recommendations
      } catch (err) {
        error.value = 'Failed to load recommendations'
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    const debouncedLoad = () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(loadRecommendations, 250)
    }

    watch(budget, debouncedLoad)

    const placeOrder = async () => {
      submitting.value = true
      error.value = null
      try {
        const items = recommendations.value.map(r => ({
          sku: r.sku,
          name: r.name,
          category: r.category,
          quantity: r.recommended_quantity,
          unit_cost: r.unit_cost,
          line_cost: r.line_cost
        }))
        const result = await api.createRestockOrder(budget.value, items)
        const deliveryDate = new Date(result.expected_delivery)
        const deliveryFormatted = isNaN(deliveryDate.getTime())
          ? result.expected_delivery
          : deliveryDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
        successMessage.value = `Order ${result.order_number} submitted successfully. Expected delivery: ${deliveryFormatted}`
        setTimeout(() => { successMessage.value = null }, 5000)
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to place order'
        console.error(err)
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      budget,
      loading,
      error,
      submitting,
      successMessage,
      summary,
      recommendations,
      totalLineCost,
      formatCurrency,
      getUrgencyClass,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-body {
  padding: 1.25rem 1.5rem;
}

.slider-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.625rem;
}

.slider-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
}

.slider-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  height: 6px;
  appearance: none;
  background: #e2e8f0;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
  margin-bottom: 1.25rem;
}

.budget-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.budget-chips {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.stat-chip {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.75rem 1.25rem;
  min-width: 140px;
}

.chip-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.chip-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.stat-chip.allocated .chip-value {
  color: #ea580c;
}

.stat-chip.remaining .chip-value {
  color: #059669;
}

.count-badge {
  display: inline-block;
  margin-left: 0.5rem;
  padding: 0.125rem 0.5rem;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
  vertical-align: middle;
}

.urgency-track {
  width: 80px;
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.urgency-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.urgency-low {
  background: #3b82f6;
}

.urgency-medium {
  background: #f59e0b;
}

.urgency-high {
  background: #ef4444;
}

.empty-state {
  padding: 3rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.938rem;
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 0 0 10px 10px;
}

.footer-total {
  font-size: 0.938rem;
  color: #475569;
}

.footer-total strong {
  color: #0f172a;
  font-size: 1rem;
}

.btn-primary {
  padding: 0.625rem 1.5rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.success-banner {
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
  font-weight: 500;
}
</style>
