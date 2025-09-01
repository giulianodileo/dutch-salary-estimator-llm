# ---- Projection Table ----
            # projection_data = []
            # for year, net_annual in res_tax.items():
            #     net_monthly = net_annual / 12
            #     disposable = net_monthly - out['essential_costs']
            #     projection_data.append({"Year": year,
            #                             "Net Monthly (€)": round(net_monthly, 0),
            #                             "Disposable Monthly (€)": round(disposable, 0)})
            # df_proj = pd.DataFrame(projection_data)
            # st.markdown("### 📈 Net Income Projection (2026–2035)")
            # st.dataframe(df_proj, use_container_width=True)

            # # ---- Projection Chart ----
            # fig = px.line(df_proj, x="Year", y=["Net Monthly (€)", "Disposable Monthly (€)"],
            #               markers=True, title="Net & Disposable Income Projection")
            # st.plotly_chart(fig, use_container_width=True)
