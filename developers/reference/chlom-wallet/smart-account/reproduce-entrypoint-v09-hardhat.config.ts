import { HardhatUserConfig } from 'hardhat/config'
import baseConfig from './hardhat.config'

const config: HardhatUserConfig = {
  ...baseConfig,
  networks: {
    ...(baseConfig.networks ?? {}),
    hardhat: {
      chainId: 11155111,
      hardfork: 'cancun'
    }
  }
}

export default config
