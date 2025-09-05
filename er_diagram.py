#!/usr/bin/env python3
"""
Generate ER Diagram for Musically Backend Database
This script creates a visual ER diagram and exports it as PDF
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np

def create_er_diagram():
    # Create figure and axis
    fig, ax = plt.subplots(1, 1, figsize=(24, 18))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 18)
    ax.axis('off')
    
    # Colors
    entity_color = '#E8F4FD'
    primary_key_color = '#FFE6E6'
    foreign_key_color = '#E6F7FF'
    
    # Entity positions (x, y, width, height)
    entities = {
        'users': (2, 14, 3.5, 4),
        'auth_users': (7, 14, 3, 3),
        'password_reset_tokens': (11, 16, 3, 2),
        'content': (2, 9, 3.5, 4),
        'playlists': (7, 9, 3, 3.5),
        'playlist_content': (11, 11, 2.5, 2),
        'creator_subscriptions': (15, 14, 3.5, 3),
        'user_subscriptions': (15, 10, 3.5, 3.5),
        'playlist_access': (11, 8, 2.5, 2.5),
        'game_sessions': (2, 4, 3.5, 3.5),
        'note_attempts': (7, 4, 3, 3),
        'reviews': (15, 6, 3.5, 3),
        'marketplace_listings': (7, 0.5, 3.5, 3)
    }
    
    # Entity fields
    entity_fields = {
        'users': [
            ('id (PK)', primary_key_color),
            ('email (UK)', entity_color),
            ('username (UK)', entity_color),
            ('signup_username', entity_color),
            ('gender', entity_color),
            ('phone_number', entity_color),
            ('country_code', entity_color),
            ('bio', entity_color),
            ('profile_image_url', entity_color),
            ('instruments_taught', entity_color),
            ('years_of_experience', entity_color),
            ('teaching_style', entity_color),
            ('location', entity_color),
            ('is_verified', entity_color),
            ('subscription_tier', entity_color),
            ('total_subscribers', entity_color),
            ('total_content_created', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ],
        'auth_users': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('auth_provider', entity_color),
            ('provider_user_id', entity_color),
            ('email', entity_color),
            ('password_hash', entity_color),
            ('is_email_verified', entity_color),
            ('last_login', entity_color),
            ('refresh_token', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ],
        'password_reset_tokens': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('token (UK)', entity_color),
            ('expires_at', entity_color),
            ('used', entity_color),
            ('created_at', entity_color)
        ],
        'content': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('title', entity_color),
            ('description', entity_color),
            ('notes_data (JSON)', entity_color),
            ('tempo', entity_color),
            ('is_public', entity_color),
            ('access_type', entity_color),
            ('tags[]', entity_color),
            ('play_count', entity_color),
            ('avg_score', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ],
        'playlists': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('title', entity_color),
            ('description', entity_color),
            ('cover_image_url', entity_color),
            ('is_public', entity_color),
            ('access_code (UK)', entity_color),
            ('subscriber_only', entity_color),
            ('student_count', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ],
        'playlist_content': [
            ('playlist_id (FK)', foreign_key_color),
            ('content_id (FK)', foreign_key_color),
            ('position', entity_color),
            ('added_at', entity_color)
        ],
        'creator_subscriptions': [
            ('id (PK)', primary_key_color),
            ('creator_id (FK,UK)', foreign_key_color),
            ('price_cents', entity_color),
            ('currency', entity_color),
            ('description', entity_color),
            ('perks[]', entity_color),
            ('is_active', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ],
        'user_subscriptions': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('creator_id (FK)', foreign_key_color),
            ('subscription_id (FK)', foreign_key_color),
            ('payment_reference', entity_color),
            ('status', entity_color),
            ('current_period_start', entity_color),
            ('current_period_end', entity_color),
            ('started_at', entity_color),
            ('cancelled_at', entity_color)
        ],
        'playlist_access': [
            ('id (PK)', primary_key_color),
            ('playlist_id (FK)', foreign_key_color),
            ('user_id (FK)', foreign_key_color),
            ('access_type', entity_color),
            ('joined_at', entity_color)
        ],
        'game_sessions': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('content_id (FK)', foreign_key_color),
            ('game_type', entity_color),
            ('difficulty', entity_color),
            ('score', entity_color),
            ('accuracy', entity_color),
            ('total_notes', entity_color),
            ('successful_notes', entity_color),
            ('time_elapsed', entity_color),
            ('device_type', entity_color),
            ('created_at', entity_color)
        ],
        'note_attempts': [
            ('id (PK)', primary_key_color),
            ('session_id (FK)', foreign_key_color),
            ('note_index', entity_color),
            ('target_pitch', entity_color),
            ('played_pitch', entity_color),
            ('expected_duration', entity_color),
            ('actual_duration', entity_color),
            ('accuracy_cents', entity_color),
            ('timestamp_in_game', entity_color),
            ('success', entity_color)
        ],
        'reviews': [
            ('id (PK)', primary_key_color),
            ('user_id (FK)', foreign_key_color),
            ('creator_id (FK)', foreign_key_color),
            ('rating', entity_color),
            ('comment', entity_color),
            ('is_verified_purchase', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ],
        'marketplace_listings': [
            ('id (PK)', primary_key_color),
            ('content_id (FK,UK)', foreign_key_color),
            ('seller_id (FK)', foreign_key_color),
            ('price_cents', entity_color),
            ('currency', entity_color),
            ('title', entity_color),
            ('description', entity_color),
            ('license_type', entity_color),
            ('sales_count', entity_color),
            ('is_active', entity_color),
            ('created_at', entity_color),
            ('updated_at', entity_color)
        ]
    }
    
    # Draw entities
    for entity_name, (x, y, width, height) in entities.items():
        # Entity box
        entity_box = FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.02",
            facecolor='white',
            edgecolor='black',
            linewidth=2
        )
        ax.add_patch(entity_box)
        
        # Entity name
        ax.text(x + width/2, y + height - 0.2, entity_name.upper().replace('_', ' '), 
                ha='center', va='center', fontsize=12, fontweight='bold')
        
        # Draw fields
        fields = entity_fields.get(entity_name, [])
        field_height = 0.15
        start_y = y + height - 0.5
        
        for i, (field_name, field_color) in enumerate(fields):
            field_y = start_y - i * field_height
            if field_y > y:  # Only draw if within entity bounds
                # Field background
                field_box = patches.Rectangle(
                    (x + 0.05, field_y - field_height/2), width - 0.1, field_height,
                    facecolor=field_color,
                    edgecolor='gray',
                    linewidth=0.5
                )
                ax.add_patch(field_box)
                
                # Field text
                ax.text(x + 0.1, field_y, field_name, 
                        ha='left', va='center', fontsize=8)
    
    # Define relationships
    relationships = [
        ('users', 'auth_users', '1:M'),
        ('users', 'password_reset_tokens', '1:M'),
        ('users', 'content', '1:M'),
        ('users', 'playlists', '1:M'),
        ('users', 'creator_subscriptions', '1:1'),
        ('users', 'user_subscriptions', '1:M'),  # as subscriber
        ('users', 'playlist_access', '1:M'),
        ('users', 'game_sessions', '1:M'),
        ('users', 'reviews', '1:M'),  # as reviewer
        ('users', 'marketplace_listings', '1:M'),
        ('content', 'playlist_content', '1:M'),
        ('content', 'game_sessions', '1:M'),
        ('content', 'marketplace_listings', '1:1'),
        ('playlists', 'playlist_content', '1:M'),
        ('playlists', 'playlist_access', '1:M'),
        ('creator_subscriptions', 'user_subscriptions', '1:M'),
        ('game_sessions', 'note_attempts', '1:M')
    ]
    
    # Draw relationships
    for entity1, entity2, cardinality in relationships:
        if entity1 in entities and entity2 in entities:
            x1, y1, w1, h1 = entities[entity1]
            x2, y2, w2, h2 = entities[entity2]
            
            # Calculate connection points
            center1_x, center1_y = x1 + w1/2, y1 + h1/2
            center2_x, center2_y = x2 + w2/2, y2 + h2/2
            
            # Simple connection line
            line = ConnectionPatch(
                (center1_x, center1_y), (center2_x, center2_y),
                "data", "data",
                arrowstyle="->",
                color='red',
                linewidth=1,
                alpha=0.7
            )
            ax.add_patch(line)
            
            # Add cardinality label
            mid_x, mid_y = (center1_x + center2_x) / 2, (center1_y + center2_y) / 2
            ax.text(mid_x, mid_y, cardinality, 
                    ha='center', va='center', fontsize=7, 
                    bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
    
    # Title
    ax.text(12, 17.5, 'MUSICALLY BACKEND - DATABASE ER DIAGRAM', 
            ha='center', va='center', fontsize=20, fontweight='bold')
    
    # Legend
    legend_x, legend_y = 19, 2
    ax.add_patch(patches.Rectangle((legend_x, legend_y), 4, 3, 
                                   facecolor='white', edgecolor='black', linewidth=1))
    ax.text(legend_x + 2, legend_y + 2.7, 'LEGEND', ha='center', va='center', 
            fontsize=12, fontweight='bold')
    
    # Legend items
    legend_items = [
        ('Primary Key (PK)', primary_key_color),
        ('Foreign Key (FK)', foreign_key_color),
        ('Regular Field', entity_color),
        ('Unique Key (UK)', entity_color)
    ]
    
    for i, (label, color) in enumerate(legend_items):
        y_pos = legend_y + 2.2 - i * 0.3
        ax.add_patch(patches.Rectangle((legend_x + 0.2, y_pos - 0.1), 0.3, 0.2, 
                                       facecolor=color, edgecolor='gray'))
        ax.text(legend_x + 0.6, y_pos, label, ha='left', va='center', fontsize=9)
    
    plt.tight_layout()
    return fig

def main():
    """Generate and save the ER diagram as PDF"""
    fig = create_er_diagram()
    
    # Save as PDF
    pdf_path = '/home/srinivasmr/PycharmProjects/musically-backend/musically_er_diagram.pdf'
    fig.savefig(pdf_path, format='pdf', dpi=300, bbox_inches='tight')
    
    print(f"ER Diagram saved as: {pdf_path}")
    plt.close(fig)

if __name__ == "__main__":
    main()