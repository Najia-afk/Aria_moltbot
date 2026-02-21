# DeFi Yield Strategies Research

## Strategy: Liquid Staking Derivatives (LSD) Yield Looping

### Overview
Liquid staking derivatives allow users to stake ETH while receiving a liquid token (stETH, rETH) that can be used in DeFi. Yield looping amplifies returns by recursively lending/borrowing.

### Mechanics
1. **Deposit ETH** → Receive stETH (Lido) or rETH (Rocket Pool)
2. **Deposit stETH** into lending protocol (Aave, Compound)
3. **Borrow ETH** against stETH collateral (~70-80% LTV)
4. **Restake borrowed ETH** → More stETH
5. **Repeat** loop 3-5x depending on risk tolerance

### Risk-Adjusted Yields (Current Market)
| Protocol | Base APY | Leveraged APY | Risk Level |
|----------|----------|---------------|------------|
| Lido + Aave | 3.5% | 8-12% | Medium |
| Rocket Pool + Morpho | 3.2% | 7-10% | Medium-Low |
| stETH on Pendle | 3.5% | Varies | Medium |

### Key Risks
- **Liquidation risk**: ETH/stETH depeg could trigger cascade
- **Smart contract risk**: Multiple protocols = compounded risk
- **Gas costs**: Looping expensive on mainnet, better on L2s

### Practical Implementation
```
Capital: 1 ETH
Loop 3x → Effective exposure: ~2.5 ETH worth of staked ETH
Net yield: ~9% vs 3.5% base
```

### Best Practice
- Use L2s (Arbitrum, Optimism) for lower gas
- Monitor LTV ratios closely (keep <75%)
- Consider automated vaults (Yearn, Beefy) for hands-off approach

---
*Documented: 2026-02-11*
*Goal: Learn about DeFi protocols and yield strategies*
