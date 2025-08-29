from whats_left_llm.calculate_30_rule import expat_ruling_calc
from whats_left_llm.chart import return_net_income

res_tax = expat_ruling_calc(35, 60000, "2025-01-01", 7, True, True)
print(res_tax)

print(return_net_income(res_tax, 1668))
