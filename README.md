# Hyperliquid Funding Arbitrage Strategy

A delta-neutral trading strategy that captures funding rate inefficiencies on Hyperliquid by maintaining balanced positions across spot and perpetual futures markets.

## Strategy Overview

This bot implements a market-neutral funding arbitrage strategy:
- **Long spot / Short perp** when funding rate is positive
- **Short spot / Long perp** when funding rate is negative
- Maintains delta-neutral positions to eliminate directional price risk
- Real-time rebalancing to preserve neutrality
- Liquidation-aware position management

## Getting Started

### 1. Deposit USDC to Hyperliquid

Before running the strategy, you need to deposit USDC from Arbitrum to Hyperliquid:

**Prerequisites:**
- USDC on Arbitrum network (minimum 5 USDC)
- Small amount of ETH on Arbitrum for gas fees
- MetaMask or compatible wallet

**Deposit Steps:**
1. Visit [https://app.hyperliquid.xyz](https://app.hyperliquid.xyz)
2. Connect your wallet (MetaMask, WalletConnect, etc.)
3. Click **"Deposit"** in the top right
4. Enter amount to deposit (minimum 5 USDC)
5. Confirm the transaction in your wallet
6. Funds arrive in ~1 minute

**Getting USDC on Arbitrum:**
- Bridge from Ethereum using [Arbitrum Bridge](https://bridge.arbitrum.io/)
- Bridge from other chains using [deBridge](https://app.debridge.finance/) or [Across](https://app.across.to/bridge)
- Buy directly on a CEX and withdraw to Arbitrum

**Important Notes:**
- ⚠️ Minimum deposit is **5 USDC** - amounts below this will be lost
- Withdrawals take ~3-4 minutes and only require a signature (no gas)
- Your Hyperliquid account address is the same as your Ethereum/Arbitrum address

### 2. Get Your Account Details

Your private key and account address are from your Ethereum/Arbitrum wallet:
- **Account Address**: Your wallet address (0x...)
- **Private Key**: Export from MetaMask or your wallet (⚠️ keep secure!)

### 3. Installation

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configuration

1. Copy `.env.example` to `.env`
2. Add your Hyperliquid private key and account address
3. Adjust strategy parameters (funding thresholds, position sizes, etc.)

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Usage

```bash
# Run the strategy
python main.py

# Dry run mode (no actual trades)
python main.py --dry-run
```

## Risk Warnings

- This strategy involves leverage and perpetual futures trading
- Always start with small position sizes
- Monitor liquidation risks carefully
- Funding rates can change rapidly
- Test thoroughly on testnet first

## Architecture

- `hyperliquid_client.py` - API wrapper for Hyperliquid
- `funding_monitor.py` - Tracks funding rates across assets
- `position_manager.py` - Manages delta-neutral positions
- `risk_manager.py` - Liquidation protection and risk controls
- `strategy.py` - Main strategy orchestrator
- `config.py` - Configuration management
