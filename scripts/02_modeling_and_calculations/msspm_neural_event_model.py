"""
MSSPM: Multi-Source Stock Movement Prediction Model
===================================================
PyTorch implementation of the dual-stream neural architecture specified in Figure 3:
1. Event Extraction Stream:
   - News Tokens -> Embedding + Bi-LSTM (H_x)
   - Self-Attention (S_x)
   - CRF / Event Role Sequence Tagger -> Role Embedding (E_e)
   - Tensor Fusion: Combines contextual token embeddings with role representations -> H'_x
2. Stock Movement Time-Series Stream:
   - Stock Multi-feature Vectors -> Bi-LSTM (H_y)
   - Self-Attention (S_y)
3. Cross-Modal Co-Attention:
   - Bilinear Affinity Matrix: A = tanh(H'_x W_xy S_y^T)
   - Cross-attended contexts: C_x (Stock conditioned on News), C_y (News conditioned on Stock)
4. Gated Sum Fusion:
   - Residual gate: G_x = z_x * H'_x + (1 - z_x) * C_x
   - Residual gate: G_y = z_y * S_y + (1 - z_y) * C_y
5. Softmax Classifier:
   - Fully connected projection -> 3-class movement prediction {Down, Neutral, Up}
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class SelfAttentionLayer(nn.Module):
    """Multi-Head Self-Attention for sequence contextualization."""
    def __init__(self, hidden_dim: int, num_heads: int = 4):
        super().__init__()
        self.mha = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=num_heads, batch_first=True)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attn_out, _ = self.mha(x, x, x)
        return self.norm(x + attn_out)


class TensorFusion(nn.Module):
    """Tensor fusion layer combining self-attended token features S_x and event role embeddings E_e."""
    def __init__(self, token_dim: int, role_dim: int, out_dim: int):
        super().__init__()
        self.proj_token = nn.Linear(token_dim, out_dim)
        self.proj_role = nn.Linear(role_dim, out_dim)
        self.fusion = nn.Sequential(
            nn.Linear(out_dim * 2, out_dim),
            nn.ReLU(),
            nn.LayerNorm(out_dim)
        )

    def forward(self, s_x: torch.Tensor, e_e: torch.Tensor) -> torch.Tensor:
        t_proj = self.proj_token(s_x)
        r_proj = self.proj_role(e_e)
        combined = torch.cat([t_proj, r_proj], dim=-1)
        return self.fusion(combined)


class CoAttentionLayer(nn.Module):
    """
    Cross-modal Co-Attention between news event representation H'_x and stock time-series S_y.
    Computes bidirectional affinity and attended context matrices C_x and C_y.
    """
    def __init__(self, dim_x: int, dim_y: int):
        super().__init__()
        self.W_xy = nn.Parameter(torch.randn(dim_x, dim_y) * 0.02)
        self.proj_x = nn.Linear(dim_y, dim_x)
        self.proj_y = nn.Linear(dim_x, dim_y)

    def forward(self, h_prime_x: torch.Tensor, s_y: torch.Tensor):
        # h_prime_x: [B, Tx, Dx]
        # s_y:       [B, Ty, Dy]
        # Affinity matrix: [B, Tx, Ty]
        aff = torch.tanh(torch.matmul(torch.matmul(h_prime_x, self.W_xy), s_y.transpose(1, 2)))
        
        # Attended stock context C_x: [B, Tx, Dy] -> projected to [B, Tx, Dx]
        alpha_y = F.softmax(aff, dim=-1) # [B, Tx, Ty]
        c_x = torch.matmul(alpha_y, s_y)
        c_x = self.proj_x(c_x)

        # Attended news context C_y: [B, Ty, Dx] -> projected to [B, Ty, Dy]
        alpha_x = F.softmax(aff.transpose(1, 2), dim=-1) # [B, Ty, Tx]
        c_y = torch.matmul(alpha_x, h_prime_x)
        c_y = self.proj_y(c_y)

        return c_x, c_y


class GatedSum(nn.Module):
    """Gated residual summation fusing original and cross-attended representations."""
    def __init__(self, dim: int):
        super().__init__()
        self.gate = nn.Sequential(
            nn.Linear(dim * 2, dim),
            nn.Sigmoid()
        )

    def forward(self, original: torch.Tensor, attended: torch.Tensor) -> torch.Tensor:
        z = self.gate(torch.cat([original, attended], dim=-1))
        return z * original + (1.0 - z) * attended


class MSSPM(nn.Module):
    """
    Full Multi-Source Stock Movement Prediction Model (Figure 3).
    """
    def __init__(
        self,
        vocab_size: int = 10000,
        news_embed_dim: int = 64,
        role_vocab_size: int = 16,
        role_embed_dim: int = 32,
        stock_feature_dim: int = 12,
        hidden_dim: int = 64,
        num_classes: int = 3
    ):
        super().__init__()
        
        # 1. Event Extraction Stream
        self.news_embedding = nn.Embedding(vocab_size, news_embed_dim, padding_idx=0)
        self.news_bilstm = nn.LSTM(news_embed_dim, hidden_dim // 2, batch_first=True, bidirectional=True)
        self.news_self_att = SelfAttentionLayer(hidden_dim)
        
        # CRF / Event Role tagger
        self.role_classifier = nn.Linear(hidden_dim, role_vocab_size)
        self.role_embedding = nn.Embedding(role_vocab_size, role_embed_dim)
        self.tensor_fuse = TensorFusion(hidden_dim, role_embed_dim, hidden_dim)
        
        # 2. Stock Movement Time-Series Stream
        self.stock_bilstm = nn.LSTM(stock_feature_dim, hidden_dim // 2, batch_first=True, bidirectional=True)
        self.stock_self_att = SelfAttentionLayer(hidden_dim)
        
        # 3. Cross-Modal Co-Attention
        self.co_attention = CoAttentionLayer(hidden_dim, hidden_dim)
        
        # 4. Gated Sum
        self.gated_sum_x = GatedSum(hidden_dim)
        self.gated_sum_y = GatedSum(hidden_dim)
        
        # 5. Output Projection
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(self, news_tokens: torch.Tensor, stock_features: torch.Tensor) -> dict:
        """
        news_tokens:    [Batch, Tx] integer token IDs
        stock_features: [Batch, Ty, NumFeatures] continuous OHLCV/indicators
        """
        # --- Event Extraction Stream ---
        e_tokens = self.news_embedding(news_tokens)
        h_x, _ = self.news_bilstm(e_tokens)
        s_x = self.news_self_att(h_x)
        
        # Event role extraction & lookup
        role_logits = self.role_classifier(s_x)
        predicted_roles = torch.argmax(role_logits, dim=-1)
        e_e = self.role_embedding(predicted_roles)
        
        # Tensor Fuse -> H'_x
        h_prime_x = self.tensor_fuse(s_x, e_e)
        
        # --- Stock Time-Series Stream ---
        h_y, _ = self.stock_bilstm(stock_features)
        s_y = self.stock_self_att(h_y)
        
        # --- Co-Attention ---
        c_x, c_y = self.co_attention(h_prime_x, s_y)
        
        # --- Gated Sum Fusion ---
        g_x = self.gated_sum_x(h_prime_x, c_x)
        g_y = self.gated_sum_y(s_y, c_y)
        
        # Pooling (mean over time dimension)
        pooled_x = g_x.mean(dim=1)
        pooled_y = g_y.mean(dim=1)
        
        # Prediction
        logits = self.classifier(torch.cat([pooled_x, pooled_y], dim=-1))
        probs = F.softmax(logits, dim=-1)
        
        return {
            "logits": logits,
            "probabilities": probs,
            "predicted_class": torch.argmax(probs, dim=-1),
            "event_role_logits": role_logits
        }


if __name__ == "__main__":
    print("Initializing MSSPM (Figure 3) Neural Architecture...")
    model = MSSPM()
    
    # Synthetic batch
    B, Tx, Ty = 4, 32, 20
    dummy_news = torch.randint(0, 1000, (B, Tx))
    dummy_stock = torch.randn(B, Ty, 12)
    
    out = model(dummy_news, dummy_stock)
    print(f"Forward pass successful!")
    print(f"Logits shape: {out['logits'].shape}")
    print(f"Probabilities: \n{out['probabilities']}")
    print(f"Predicted movement classes (0=Down, 1=Neutral, 2=Up): {out['predicted_class']}")
